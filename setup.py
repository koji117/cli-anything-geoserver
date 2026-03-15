from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-geoserver",
    version="1.0.0",
    description="CLI harness for GeoServer geospatial server",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    install_requires=[
        "click>=8.0.0",
        "prompt-toolkit>=3.0.0",
        "requests>=2.28.0",
    ],
    entry_points={
        "console_scripts": [
            "cli-anything-geoserver=cli_anything.geoserver.geoserver_cli:main",
        ],
    },
    python_requires=">=3.10",
)
