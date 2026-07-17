from setuptools import setup, find_packages

setup(
    name="adcast-agent",
    version="0.1.0",
    description="AI驱动的自动广告投放Agent - 智能选择最优广告平台",
    author="AdCast Team",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.10",
    install_requires=[
        "pyyaml>=6.0",
        "python-dotenv>=1.0.0",
        "aiohttp>=3.9.0",
        "aiofiles>=23.0.0",
        "pandas>=2.0.0",
        "numpy>=1.24.0",
    ],
    entry_points={
        "console_scripts": [
            "adcast=adcast_agent.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
