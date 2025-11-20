"""Test file to verify pre-commit hooks run during commits."""

# This file has intentional issues for pre-commit to catch


def bad_function():
    """Function with bad formatting."""
    x = 1 + 2  # No spaces around operators
    y = 3  # Extra spaces
    return x, y


if __name__ == '__main__':
    print('Testing pre-commit hooks')
