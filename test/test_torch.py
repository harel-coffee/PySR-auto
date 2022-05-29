import unittest
import numpy as np
import pandas as pd
from pysr import sympy2torch, PySRRegressor
import sympy
from functools import partial


class TestTorch(unittest.TestCase):
    def setUp(self):
        np.random.seed(0)

    def test_sympy2torch(self):
        x, y, z = sympy.symbols("x y z")
        cosx = 1.0 * sympy.cos(x) + y

        import torch
        X = torch.tensor(np.random.randn(1000, 3))
        true = 1.0 * torch.cos(X[:, 0]) + X[:, 1]
        torch_module = sympy2torch(cosx, [x, y, z])
        self.assertTrue(
            np.all(np.isclose(torch_module(X).detach().numpy(), true.detach().numpy()))
        )

    def test_pipeline_pandas(self):
        X = pd.DataFrame(np.random.randn(100, 10))
        equations = pd.DataFrame(
            {
                "Equation": ["1.0", "cos(x1)", "square(cos(x1))"],
                "MSE": [1.0, 0.1, 1e-5],
                "Complexity": [1, 2, 3],
            }
        )

        equations["Complexity MSE Equation".split(" ")].to_csv(
            "equation_file.csv.bkup", sep="|"
        )

        model = PySRRegressor(
            model_selection="accuracy",
            equation_file="equation_file.csv",
            extra_sympy_mappings={},
            output_torch_format=True,
        )
        # Because a model hasn't been fit via the `fit` method, some
        # attributes will not/cannot be set. For the purpose of
        # testing, these attributes will be set manually here.
        model.fit(X, y=np.ones(X.shape[0]), from_equation_file=True)
        model.refresh()

        tformat = model.pytorch()
        self.assertEqual(str(tformat), "_SingleSymPyModule(expression=cos(x1)**2)")
        import torch

        np.testing.assert_almost_equal(
            tformat(torch.tensor(X.values)).detach().numpy(),
            np.square(np.cos(X.values[:, 1])),  # Selection 1st feature
            decimal=4,
        )

    def test_pipeline(self):
        X = np.random.randn(100, 10)
        equations = pd.DataFrame(
            {
                "Equation": ["1.0", "cos(x1)", "square(cos(x1))"],
                "MSE": [1.0, 0.1, 1e-5],
                "Complexity": [1, 2, 3],
            }
        )

        equations["Complexity MSE Equation".split(" ")].to_csv(
            "equation_file.csv.bkup", sep="|"
        )

        model = PySRRegressor(
            model_selection="accuracy",
            equation_file="equation_file.csv",
            extra_sympy_mappings={},
            output_torch_format=True,
        )

        model.fit(X, y=np.ones(X.shape[0]), from_equation_file=True)
        model.refresh()

        tformat = model.pytorch()
        self.assertEqual(str(tformat), "_SingleSymPyModule(expression=cos(x1)**2)")

        import torch
        np.testing.assert_almost_equal(
            tformat(torch.tensor(X)).detach().numpy(),
            np.square(np.cos(X[:, 1])),  # 2nd feature
            decimal=4,
        )

    def test_mod_mapping(self):
        x, y, z = sympy.symbols("x y z")
        expression = x**2 + sympy.atanh(sympy.Mod(y + 1, 2) - 1) * 3.2 * z

        module = sympy2torch(expression, [x, y, z])

        import torch
        X = torch.rand(100, 3).float() * 10

        true_out = (
            X[:, 0] ** 2 + torch.atanh(torch.fmod(X[:, 1] + 1, 2) - 1) * 3.2 * X[:, 2]
        )
        torch_out = module(X)

        np.testing.assert_array_almost_equal(
            true_out.detach(), torch_out.detach(), decimal=4
        )

    def test_custom_operator(self):
        X = np.random.randn(100, 3)

        equations = pd.DataFrame(
            {
                "Equation": ["1.0", "mycustomoperator(x1)"],
                "MSE": [1.0, 0.1],
                "Complexity": [1, 2],
            }
        )

        equations["Complexity MSE Equation".split(" ")].to_csv(
            "equation_file_custom_operator.csv.bkup", sep="|"
        )

        import torch
        model = PySRRegressor(
            model_selection="accuracy",
            equation_file="equation_file_custom_operator.csv",
            extra_sympy_mappings={"mycustomoperator": sympy.sin},
            extra_torch_mappings={"mycustomoperator": torch.sin},
            output_torch_format=True,
        )
        model.fit(X, y=np.ones(X.shape[0]), from_equation_file=True)
        model.refresh()
        self.assertEqual(str(model.sympy()), "sin(x1)")
        # Will automatically use the set global state from get_hof.

        tformat = model.pytorch()
        self.assertEqual(str(tformat), "_SingleSymPyModule(expression=sin(x1))")
        np.testing.assert_almost_equal(
            tformat(torch.tensor(X)).detach().numpy(),
            np.sin(X[:, 1]),
            decimal=4,
        )

    def test_feature_selection(self):
        X = pd.DataFrame({f"k{i}": np.random.randn(1000) for i in range(10, 21)})
        y = X["k15"] ** 2 + np.cos(X["k20"])

        model = PySRRegressor(
            unary_operators=["cos"],
            select_k_features=3,
            early_stop_condition=1e-5,
        )
        model.fit(X.values, y.values)
        torch_module = model.pytorch()

        np_output = model.predict(X.values)
        import torch
        torch_output = torch_module(torch.tensor(X.values)).detach().numpy()

        np.testing.assert_almost_equal(np_output, torch_output, decimal=4)
