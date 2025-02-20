# SpreadLine
A visualization design framework that supports the exploration of dynamic multivariate networks from the egocentric perspective.
This repo is part of the research paper "SpreadLine: Visualizing Egocentric Dynamic Influence" ([link](https://ieeexplore.ieee.org/document/10680192)), published in IEEE Transactions on Visualization and Computer Graphics.

## Introduction
- Source code can be found in `./SpreadLine`
- Sample script of using SpreadLine refers to `./sample.py`
- `supplementary_materials.pdf` contains 5 major sections: (A) Examples of different optimization focuses, optimization details, and two more discussions on design choices; (B) Interface of using SpreadLine; (C) Data structures of all three case studies and their associated ChatGPT prompts for data processing (if there is any); (D) Self-reported participant background & additional usability study details; (E) Two more SpreadLine representations of visualization researchers on a larger data scale.
- `./case-studies` provide the datasets used in SpreadLine representations.
- `./demo` contains a vanilla web application that computes and renders SpreadLine representations.

## Python Installation
Run this to use SpreadLine as demonstrated in `./sample.py`
```
pip install .
```


## Roadmap
- Code documentations and cleanup.

## How to Cite
If you use any parts of this repo, please cite:
```
Kuo, Y.-H., Liu, D., & Ma, K.-L. (2024). SpreadLine: Visualizing egocentric dynamic influence. IEEE Transactions on Visualization and Computer Graphics.
```
or in bibtex:
```
@article{kuo2024spreadline,
  title={SpreadLine: Visualizing egocentric dynamic influence},
  author={Kuo, Yun-Hsin and Liu, Dongyu and Ma, Kwan-Liu},
  journal={IEEE Transactions on Visualization and Computer Graphics},
  year={2024},
  publisher={IEEE}
}
```
