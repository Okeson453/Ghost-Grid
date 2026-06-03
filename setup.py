from setuptools import setup, find_packages

setup(
    name="ghost_grid",
    version="0.1.0",
    description="Personal MT5 scalping system — confluence-driven H_c scoring",
    author="Solo Developer",
    packages=find_packages(exclude=["tests", "data_store", "logs"]),
    python_requires=">=3.11",
    install_requires=[
        "uvloop>=0.19.0",
        "asyncio-throttle>=1.0.2",
        "numpy>=1.26.4",
        "pandas>=2.2.2",
        "ta-lib>=0.4.32",
        "pandas-ta>=0.3.14b0",
        "pywin32>=306",
        "aiosqlite>=0.20.0",
        "python-telegram-bot>=21.3",
        "python-dotenv>=1.0.1",
        "structlog>=24.1.0",
        "backtrader>=1.9.78.123",
    ],
    extras_require={
        "dev": [
            "pytest>=8.2.0",
            "pytest-asyncio>=0.23.7",
            "pytest-mock>=3.14.0",
            "freezegun>=1.5.0",
            "mypy>=1.10.0",
            "ruff>=0.4.4",
        ],
    },
)
