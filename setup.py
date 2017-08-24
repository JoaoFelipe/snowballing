import os
from setuptools import setup, find_packages


try:
    import pypandoc
    long_description = pypandoc.convert('README.md', 'rst').replace("\r", "")
except (IOError, ImportError):
    print("pypandoc not found!")
    long_description = "Provides tools for literature snowballing"


setup(
    name="Snowballing",
    version="0.1.10",
    url="https://github.com/JoaoFelipe/snowballing",
    description="Provides tools for literature snowballing",
    long_description=long_description,
    packages=find_packages(),
    author=("Joao Felipe Pimentel",),
    author_email="joaofelipenp@gmail.com",
    license="MIT",
    keywords="snowballing literature paper article scholar",
    python_requires='>=3.5',
    install_requires=[
        'ipython',
        'jupyter',
        'ipywidgets>=7.0.0',
        'pyposast',
        'svgwrite',
        'bibtexparser',
        'bs4',
        'selenium',
        'svgwrite',
        'matplotlib',
        'pandas',
        'seaborn',
        'numpy',
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',

        'Intended Audience :: Science/Research',
        'Topic :: Scientific/Engineering',

        'License :: OSI Approved :: MIT License',

        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    entry_points={
        'console_scripts': [
            'snowballing=snowballing:main',
        ],
    },
)
