from setuptools import setup, find_packages

setup(
    name='SpreadLine',
    version='0.1.0',
    packages=find_packages(where='.', include=['SpreadLine', 'SpreadLine.*']),
    install_requires=[
        "pandas", "numpy", "scipy", "scikit-learn"
    ],    
    author='Yun-Hsin Kuo',
    author_email='yskuo@ucdavis.edu',
)