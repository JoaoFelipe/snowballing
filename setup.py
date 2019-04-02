import os
from setuptools import setup, find_packages


def recursive_path(pack, path):
    matches = []
    for root, dirnames, filenames in os.walk(os.path.join(pack, path)):
        for filename in filenames:
            matches.append(os.path.join(root, filename)[len(pack) + 1:])
    return matches


try:
    import pypandoc
    long_description = pypandoc.convert('README.md', 'rst').replace("\r", "")
except (IOError, ImportError):
    print("pypandoc not found!")
    long_description = "Provides tools for literature snowballing"


setup(
    name="Snowballing",
    version="0.2.5",
    url="https://github.com/JoaoFelipe/snowballing",
    description="Provides tools for literature snowballing",
    long_description=long_description,
    packages=find_packages(),
    package_data={
        "snowballing": (
            recursive_path("snowballing", "example")
        ),
    },
    author=("Joao Felipe Pimentel",),
    author_email="joaofelipenp@gmail.com",
    license="MIT",
    keywords="snowballing literature paper article scholar",
    python_requires='>=3.5',
    install_requires=[
        'ipython',
        'jupyter',
        'ipywidgets>=7.4.2',
        'pyposast',
        'svgwrite',
        'bibtexparser>=1.1.0',
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
