import pandas as pd 
import glob 

files = glob.glob("storm-risk-ai/data/raw/*.csv.gz")

dfs = []

for file in files: 
    df = pd.read_csv(file, compression = "gzip", low_memory= False)
    dfs.append(df)

storms = pd.concat(dfs, ignore_index = True)

storms.to_csv("storm-risk-ai/data/processed/storms_2000_2026.csv", index=False)

storms.shape
storms.columns
storms.head()




