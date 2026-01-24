import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import sympy as sp
import numpy as np
import os
import uuid

# Mimi's Visualizer Theme
THEME_COLOR = "#00BFFF"  # A nice blue for Mimi


def visualize_math(action, formula, x_range=(-10, 10)):
    """
    Generates a math image.
    action: 'render' (for LaTeX) or 'plot' (for graphs)
    formula: The LaTeX string or pythonic math expression (e.g. 'sin(x)')
    x_range: Tuple for plotting range
    """
    file_id = str(uuid.uuid4())
    temp_filename = f"math_{file_id}.png"

    try:
        if action == "render":
            # Fix formula if it doesn't have $ wrappers
            clean_formula = formula.strip()
            if not clean_formula.startswith("$"):
                clean_formula = f"${clean_formula}$"

            # Simple LaTeX renderer
            fig = plt.figure(figsize=(1, 1))  # Dummy size, will be tight
            fig.text(
                0.5,
                0.5,
                clean_formula,
                size=24,
                ha="center",
                va="center",
                color="black",
            )
            plt.axis("off")
            plt.savefig(
                temp_filename,
                bbox_inches="tight",
                transparent=False,
                facecolor="white",
                dpi=200,
            )
            plt.close(fig)

        elif action == "plot":
            x = sp.symbols("x")
            # Parse expression
            expr = sp.sympify(formula)
            f = sp.lambdify(x, expr, "numpy")

            x_vals = np.linspace(x_range[0], x_range[1], 500)
            y_vals = f(x_vals)

            fig, ax = plt.subplots(figsize=(8, 5))
            ax.plot(
                x_vals,
                y_vals,
                color=THEME_COLOR,
                linewidth=2.5,
                label=f"y = {sp.latex(expr)}",
            )

            # Formatting
            ax.grid(True, linestyle=":", alpha=0.6)
            ax.axhline(0, color="black", linewidth=1.2)
            ax.axvline(0, color="black", linewidth=1.2)
            ax.set_title(f"Mimi's Sketch: ${sp.latex(expr)}$", fontsize=14)
            ax.legend()

            plt.savefig(temp_filename, bbox_inches="tight", dpi=150)
            plt.close(fig)

        return temp_filename
    except Exception as e:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
        raise e


def cleanup(filename):
    if filename and os.path.exists(filename):
        os.remove(filename)
