# UPD-3D
Code for generating samples to test 3D-LLM unsolvable problem detection capability.

## Create a Conda environment
```
conda create -n upd-3d python=3.12
```

## Activate the Conda environment
```
conda activate upd-3d
```

## Link the 3D-GRAND dataset
Create a soft link to the 3D-GRAND dataset in the project directory. The link should be named `data`:
```
ln -s /path/to/3D-GRAND data
```
Replace `/path/to/3D-GRAND` with the actual path to the 3D-GRAND dataset on your system. You can download the dataset from [Hugging Face](https://huggingface.co/datasets/sled-umich/3D-GRAND/tree/main). The data link should point to the top level of 3D-GRAND that looks like this:

```
3d-grand/
├── .cache/
├── code/
├── data/
├── .gitattributes
├── LICENSE
└── README.md
```

So if you cd into the soft-link "data", you should see .cache, code/, data/, etc.

Inside the pcl/ folder, you can manually make subsets of point clouds for UPD question 
generation.
For example, create a file inside called "v1.txt" and then list some point clouds from 
3D-GRAND inside.

```
LivingRoom-52289
Bedroom-516
...
```