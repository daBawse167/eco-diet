import os
import numpy as np
import pandas as pd
import statistics as stats
from flask import Flask, request, jsonify

app = Flask(__name__)

app.config["SECRET_KEY"] = os.urandom(64)
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = "./.flask_session/"


@app.route("/recommend", methods=["GET"])
def create_recommendations():
    country_name = str(request.args.get("country_name"))
    print(country_name)
    
    chickens = int(request.args.get("chickens"))
    cattle = int(request.args.get("cattle"))
    goats = int(request.args.get("goats"))
    sheep = int(request.args.get("sheep"))
    swine = int(request.args.get("swine"))
    buffalo = int(request.args.get("buffalo"))

    eaten = {'Chicken':chickens, 'Buffalo':buffalo,
             'Cow':cattle, 'Goat':goats, 'Sheep':sheep, 'Pig':swine}
    print(eaten)
    
    percent_reduction = 0.5
    
    return_animals = find_stock(country_name=country_name, eaten=eaten)
    animals_eaten, options = return_animals[0], return_animals[1]
    
    #find the target emissions
    total_emitted = sum(animals_eaten["weekly_emitted (kg/animal)"])
    target = (1-percent_reduction)*total_emitted

    print(total_emitted)
    
    low_carbon = []
    i = 0
    #gets the animals with GHG lower than the target
    for option in options:
        if option <= target:
            low_carbon.append([animals_eaten["Item"].iloc[i], option])
        i += 1
        
    #in case no choice is made, get the min red and white meat animals
    white_meat = ['Chicken']
    red_meat = ['Cow', 'Goat', 'Sheep', 'Pig', 'Buffalo']
    
    white_meat_options_list = [i for i in low_carbon if i[0] in white_meat]
    red_meat_options_list = [i for i in low_carbon if i[0] in red_meat]
    
    if len(white_meat_options_list)==0 and len(red_meat_options_list)==0:
        return {"emitted (kg)":0, "target (kg)":0,
                'Chicken': 0, 'Buffalo': 0, 'Cow': 0, 'Goat': 0, 'Sheep': 0, 'Pig': 0,
                "cattle_e":0, "chickens_e":0, "buffalo_e":0, "goats_e":0, "sheep_e":0, "swine_e":0}
    
    red_meat_options = {"animal":[], "emissions":[]}
    white_meat_options = {"animal":[], "emissions":[]}
    
    if len(red_meat_options) > 0:
        red_meat_options = {"animal": np.array(red_meat_options_list).T[0], "emissions": np.array(red_meat_options_list).T[1]}
        red_meat_options = pd.DataFrame(red_meat_options).sort_values(ascending=True, by="emissions")
    if len(white_meat_options) > 0:
        white_meat_options = {"animal": np.array(white_meat_options_list).T[0], "emissions": np.array(white_meat_options_list).T[1]}
        white_meat_options = pd.DataFrame(white_meat_options).sort_values(ascending=True, by="emissions")
    
    print(red_meat_options, white_meat_options)
    
    
    idx = 0
    recommend_list = {"emitted (kg)":round(total_emitted, 3),
                      "target (kg)":0,
                     'Chicken': 0,
                     'Buffalo': 0,
                     'Cow': 0,
                     'Goat': 0,
                     'Sheep': 0,
                     'Pig': 0}
    emissions_counter = 0
    white_meat_counter = 0
    red_meat_counter = 0
    
    white_meat_max = 340
    red_meat_max = 500
    portion = 85
    
    #want to recommend at least 85g per animal
    #want to have a variety in the animals
    #want to include both red and white meat
    #want to obey the limits of red and white meat
    
    #look at first red meat option
    #add 85g of meat & record emission
    #look at first white meat option
    #add 85g of meat & record emission
    #repeat until emission is low or meat limit reached
    
    red_idx = 0
    white_idx = 0
    
    #make sure we don't break white & red meat's limits
    white_limit = False
    red_limit = False
    
    while emissions_counter < target:

        #make sure white and red idx don't get out of range
        if red_idx>=len(red_meat_options):
            red_idx = 0
        if white_idx>=len(white_meat_options):
            white_idx = 0
        
        #break if no. grams is exceeded
        if white_limit:
            if red_limit:
                break
        
        if white_meat_counter < white_meat_max and len(white_meat_options_list) > 0:
            #add 1 portion of white meat & its emissions
            meat_emission = float(white_meat_options.iloc[white_idx]["emissions"])
            animal = white_meat_options.iloc[white_idx]["animal"]

            if emissions_counter+(meat_emission*portion) < target:
                emissions_counter += meat_emission*portion
                white_meat_counter += portion
                recommend_list[animal] += portion
            else:
                #round up to 50% less emissions
                portion = np.floor((target-emissions_counter)/meat_emission)
                emissions_counter += meat_emission*portion
                white_meat_counter += portion
                recommend_list[animal] += portion
                break
        else:
            white_limit = True
        
        if red_meat_counter < red_meat_max and len(red_meat_options_list) > 0:
            #add 1 portion of red meat & its emissions
            meat_emission = float(red_meat_options.iloc[red_idx]["emissions"])
            animal = red_meat_options.iloc[red_idx]["animal"]

            if emissions_counter+(meat_emission*portion) < target:
                emissions_counter += meat_emission*portion
                red_meat_counter += portion
                recommend_list[animal] += portion
            else:
                #round up to 50% less emissions
                portion = np.floor((target-emissions_counter)/meat_emission)
                emissions_counter += meat_emission*portion
                red_meat_counter += portion
                recommend_list[animal] += portion
                break
        else:
            red_limit = True
        
        
        red_idx += 1
        white_idx += 1
    
    recommend_list["target (kg)"] = round(emissions_counter, 3)
    
    #show the emissions of ALL animals
    animals_eaten.index=animals_eaten["Item"]
    animals_eaten = animals_eaten["emissions (per kg)"]
    
    #present each animal's recommended emissions
    animals_e = {"Cow":0, "Chicken":0, "Buffalo":0, "Goat":0, "Sheep":0, "Pig":0}
    
    for i in animals_eaten.index:
        animals_e[i] = round(animals_eaten.loc[i]*(recommend_list[i]/1000), 3)
        
    #fills in animals not listed in country
    for idx in white_meat+red_meat:
        if idx not in list(animals_e.keys()):
            animals_e[idx] = 0
    
    #adds emissions to output dictionary
    recommend_list["cattle_e"] = animals_e["Cow"]
    recommend_list["chickens_e"] = animals_e["Chicken"]
    recommend_list["buffalo_e"] = animals_e["Buffalo"]
    recommend_list["goats_e"] = animals_e["Goat"]
    recommend_list["sheep_e"] = animals_e["Sheep"]
    recommend_list["swine_e"] = animals_e["Pig"]
    
    return recommend_list



def find_stock(country_name="", eaten={}):
    #get FAOSTAT data
    faostat = pd.read_csv("FAOSTAT.csv")
    faostat = faostat[['Area', 'Item', 'Value']]
    faostat["emissions (per kg)"] = faostat["Value"]
    faostat = faostat.drop("Value", axis=1)
    
    #change animals names
    faostat["Item"] = faostat["Item"].replace("Meat of cattle with the bone, fresh or chilled", "Cow")
    faostat["Item"] = faostat["Item"].replace("Meat of goat, fresh or chilled", "Goat")
    faostat["Item"] = faostat["Item"].replace("Meat of buffalo, fresh or chilled", "Buffalo")
    faostat["Item"] = faostat["Item"].replace("Meat of sheep, fresh or chilled", "Sheep")
    faostat["Item"] = faostat["Item"].replace("Meat of chickens, fresh or chilled", "Chicken")
    faostat["Item"] = faostat["Item"].replace("Meat of pig with the bone, fresh or chilled", "Pig")
    
    #loop over country
    country_df = faostat[faostat["Area"]==country_name]

    print(country_df)
    
    emissions_per_gram_list = []
    weekly_emitted = []
    
    for i in list(country_df["Item"]):
        #get the emissions per gram and weekly emitted
        idx = list(country_df["Item"]).index(i)
        emissions_per_gram = country_df["emissions (per kg)"].iloc[idx] / 1000
        print(emissions_per_gram)
        
        emissions_per_gram_list.append(emissions_per_gram)
        weekly_emitted.append(round(emissions_per_gram*eaten[i], 2))
    
    #add the columns to the dataset
    country_df["emissions (per gram)"] = emissions_per_gram_list
    country_df["weekly_emitted (kg/animal)"] = weekly_emitted
    
    return [country_df, list(country_df["emissions (per gram)"])]

@app.route('/present', methods=["GET"])
def present():
    country = request.args.get("country")
    
    total_df = pd.read_csv("FAOSTAT.csv")
    total_df["Item"] = total_df["Item"].replace("Meat of cattle with the bone, fresh or chilled", "Cow")
    total_df["Item"] = total_df["Item"].replace("Meat of goat, fresh or chilled", "Goat")
    total_df["Item"] = total_df["Item"].replace("Meat of buffalo, fresh or chilled", "Buffalo")
    total_df["Item"] = total_df["Item"].replace("Meat of sheep, fresh or chilled", "Sheep")
    total_df["Item"] = total_df["Item"].replace("Meat of chickens, fresh or chilled", "Chicken")
    total_df["Item"] = total_df["Item"].replace("Meat of pig with the bone, fresh or chilled", "Pig")

    countries = list(np.unique(total_df["Area"]))
    animals = list(np.unique(total_df[total_df["Area"]==country]["Item"]))
    present = []

    for animal in ['Buffalo', 'Chicken', 'Cow', 'Goat', 'Pig', 'Sheep']:
        present.append(animal in animals)

    return {'Buffalo':present[0], 'Chicken':present[1], 'Cow':present[2], 'Goat':present[3], 'Pig':present[4], 'Sheep':present[5]}

if __name__=="__main__":
    app.run(debug=True)
