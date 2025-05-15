# UPD-3D
Code for generating samples to test 3D-LLM unsolvable problem detection capability.

## Clone

```
git clone https://github.com/Mikey-E/UPD-3D.git
cd UPD-3D
```

## Create a Conda environment
```
conda create -n upd-3d python=3.12
```

## Activate the Conda environment
```
conda activate upd-3d
```

## Install dependencies

```
conda install openai=1.60.1 matplotlib=3.10.0
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

So if you cd into the soft-link "data", you should see .cache, code/, data/, etc. Note that you will need to have folder *unzipped* for the point clouds to be reachable. You do not necessarily have to do this all at once if you are interested in working with just a subset of 3D-GRAND for UPD dataset creation.

## Choosing a set of scenes to use

Inside the pcl/ folder, you can manually make subsets of point clouds for UPD question 
generation.
For example, create a file inside called "the_first_set_of_clouds.txt" and then list some point clouds from 
3D-GRAND inside.

```
8ef1ac63-da17-4f85-94ad-d784649329c6@Bedroom-206
55f2b905-d367-443d-8f88-ef71b958c81f@LivingRoom-3973
...
```

As an alternative to manually choosing your scenes, you can unzip a 3D-FRONT zip file from the 3D-GRAND data and use make_pcl_list.py to generate a list of all the scenes there for your use:

```
python make_pcl_list.py list_of_clouds.txt path/to/unzipped/3D-FRONT/data
```

## Gathering the text description of each scene

Now that you have your list of scenes to use as a basis for this new dataset, the 
text description of each scene will be needed to later generate questions for it. 
gather_scene_info.py will get these text descriptions. Simply pass it the text file that you created from the last step:

```
python gather_scene_info.py list_of_clouds.txt
```

Now the text description of each has been gathered in text_basis/

## Setting an OpenAI API key

Further steps will require an OpenAI API key.
Make sure your account has funds. $5 is more than enough for a set of 1,200 samples.

```
export OPENAI_API_KEY=sk-proj-epoTPF...
```

## Make the multiple-choice questions

make_mc_text.py will take the name of the folder inside text_basis/ and create the standard_answer subset inside upd_text/. This is a subset containing multiple choice questions based on the descriptions, including the correct answer.

```
python make_mc_text.py list_of_clouds
```

## Make the open-ended questions

This can be done like it was done for multiple-choice questions:

```
python make_oe_text.py list_of_clouds
```

## Separate out an answer key

It is necessary to have an answer key for each scene's standard question for use in later computations. create_answer_key.py will separate this out and store it.

```
python create_answer_key.py upd_text/list_of_clouds
```

## Make the UPD variants

This requires the multiple-choice and open-ended questions to have been generated first. Simply run:

```
python make_variants.py list_of_clouds
```

If all you want is the dataset, you are now finished! The UPD-3D dataset is now in upd_text/

## Obtaining model repsonses from MiniGPT-3D

This requires a separate working installation of
[MiniGPT-3D](https://github.com/TangYuan96/MiniGPT-3D).
There is a utils file mod_demo.py (short for modified demo) here in UPD-3D based 
on the UI_demo.py file from MiniGPT-3D. It modifies the gradio demo to allow 
uploading the list of scenes in pcl_lists, as well as setting the path to
the unzipped 3D-FRONT scenes and setting the path to a particular UPD subset.
MiniGPT-3D will then make responses to that entire batch. The output of that will 
be placed in the top-level of MiniGPT-3D. It should then be copied to the folder
unscored_model_responses/ (here in UPD-3D) or perhaps a subfolder within it - 
however you want to stay organized.

*Any* LLM, so long as it produces a json file of a dictionary where the key is
the scene and the value is a dictionary of prompt and response (as seen there), 
can have its
output placed in unscored_model_responses/ for further evaluation.

## Scoring the model responses

This can be done with score_model_responses.py. For example:

```
python score_model_responses.py unscored_model_responses/v1_MiniGPT-3D/inference_results_MiniGPT-3D_v1_aad_additional_option.json 
```

This will place a scored version in scored_model_responses/. You'll want to do 
this for every unscored subset file before proceeding. For the standard subset, be
sure to pass the path to the answer key with --answer_key.

## Analyze the results

analyze_scored_responses.py will take a path to the directory of scored response 
json files, and create a graph in results/

```
python analyze_scored_responses.py path/to/scored/json/files --naming_delim _v1_
```

where --naming_delim specifices a delimiter in the file names between the subset 
name and the rest of the file name. This helps to make clean labels on the graph.