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
    percent_reduction = 0.5
    
    return_animals = find_stock(country_name=country_name, eaten=eaten)
    animals_eaten, options = return_animals[0], return_animals[1]
    
    #find the target emissions
    total_emitted = sum(animals_eaten["weekly_emitted (kg/animal)"])
    target = (1-percent_reduction)*total_emitted
    
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
    
    white_meat_options = [i for i in low_carbon if i[0] in white_meat]
    red_meat_options = [i for i in low_carbon if i[0] in red_meat]
    
    red_meat_options = {"animal": np.array(red_meat_options).T[0], "emissions": np.array(red_meat_options).T[1]}
    white_meat_options = {"animal": np.array(white_meat_options).T[0], "emissions": np.array(white_meat_options).T[1]}
    
    red_meat_options = pd.DataFrame(red_meat_options).sort_values(ascending=True, by="emissions")
    white_meat_options = pd.DataFrame(white_meat_options).sort_values(ascending=True, by="emissions")
    
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
        
        if white_meat_counter < white_meat_max:
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
        
        if red_meat_counter < red_meat_max:
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
    
    emissions_per_gram_list = []
    weekly_emitted = []
    
    for i in list(country_df["Item"]):
        #get the emissions per gram and weekly emitted
        idx = list(country_df["Item"]).index(i)
        emissions_per_gram = country_df["emissions (per kg)"].iloc[idx] / 1000
        
        emissions_per_gram_list.append(emissions_per_gram)
        weekly_emitted.append(round(emissions_per_gram*eaten[i], 2))
    
    #add the columns to the dataset
    country_df["emissions (per gram)"] = emissions_per_gram_list
    country_df["weekly_emitted (kg/animal)"] = weekly_emitted
    
    return [country_df, list(country_df["emissions (per gram)"])]



def clean_data():
    #creating stock dataset
    stock = pd.read_csv("stock.csv")
    stock["Item"] = stock["Item"].replace("Cattle, dairy", "Cattle")
    stock["Item"] = stock["Item"].replace("Cattle, non-dairy", "Cattle")
    stock["Item"] = stock["Item"].replace("Swine, breeding", "Swine")
    stock["Item"] = stock["Item"].replace("Swine, market", "Swine")
    stock["Item"] = stock["Item"].replace("Chickens, broilers", "Chickens")

    #remove useless animals from dataset
    animals = [
    'Cattle, dairy', 'Cattle, non-dairy',
    'Swine, breeding', 'Swine, market',
    'Goats',
    'Sheep',

    'Chickens, broilers',
    'Ducks',
    'Turkeys']
    countries = np.unique(total_df["Area"])

    df = pd.DataFrame([i for i in total_df.iloc if i["Item"] in animals])

    df_n20 = pd.DataFrame([i for i in df.iloc if i["Element"]=="Livestock total (Emissions N2O)"])
    df_ch4 = pd.DataFrame([i for i in df.iloc if i["Element"]=="Livestock total (Emissions CH4)"])

    for gas in ["n20", "ch4"]:
        total_cattle = []
        total_swine = []
        for country in countries:
            if gas=="n20":
                country_df = df_n20[df_n20["Area"]==country]
            else:
                country_df = df_ch4[df_ch4["Area"]==country]
            #gets all cattle and swine in that country
            cattle = [i for i in country_df.iloc if i["Item"]=="Cattle, dairy" or i["Item"]=="Cattle, non-dairy"]
            swine = [i for i in country_df.iloc if i["Item"]=="Swine, breeding" or i["Item"]=="Swine, market"]

            value_c = 0
            for i in cattle:
                value_c += i["Value"]

            value_s = 0
            for i in swine:
                value_s += i["Value"]

            if len(cattle)>0:
                new_cattle = cattle[0]
                new_cattle["Item"] = "Cattle"
                new_cattle["Value"] = value_c
                new_cattle["Area"] = country
                total_cattle.append(new_cattle)

            if len(swine)>0:
                new_swine = swine[0]
                new_swine["Item"] = "Swine"
                new_swine["Value"] = value_s
                new_swine["Area"] = country
                total_swine.append(new_swine)

        total_cattle = pd.DataFrame(total_cattle)
        total_swine = pd.DataFrame(total_swine)

        if gas=="n20":
            df_n20 = df_n20[df_n20["Item"]!="Cattle, dairy"]
            df_n20 = df_n20[df_n20["Item"]!="Cattle, non-dairy"]
            df_n20 = df_n20[df_n20["Item"]!="Swine, breeding"]
            df_n20 = df_n20[df_n20["Item"]!="Swine, market"]

            df_n20 = pd.concat([df_n20, total_cattle])
            df_n20 = pd.concat([df_n20, total_swine])
        else:
            df_ch4 = df_ch4[df_ch4["Item"]!="Cattle, dairy"]
            df_ch4 = df_ch4[df_ch4["Item"]!="Cattle, non-dairy"]
            df_ch4 = df_ch4[df_ch4["Item"]!="Swine, breeding"]
            df_ch4 = df_ch4[df_ch4["Item"]!="Swine, market"]

            df_ch4 = pd.concat([df_ch4, total_cattle])
            df_ch4 = pd.concat([df_ch4, total_swine])

    #adjusting Global Warming Potential for N2O and CH4
    #N2O has ~300x more impact than CO2, & CH4 ~28 over 100 years
    df_n20["Value"] = df_n20["Value"]*300
    df_ch4["Value"] = df_ch4["Value"]*28
    data = pd.concat([df_n20, df_ch4])
    data = data[["Area", "Item", "Value"]]

    #merging all NO2 & CH4 like-animals together
    temp = pd.DataFrame({"Area":[], "Item":[], "Value":[]})
    for country_n in np.unique(data["Area"]):
        country = data[data["Area"]==country_n]
        idxes = country.groupby(by="Item").indices

        for i in idxes:
            animal = country.iloc[idxes[i]]
            temp = pd.concat([temp, (pd.DataFrame({"Area":list(animal["Area"])[0], "Item":list(animal["Item"])[0],
                             "Value":round(sum(animal["Value"]), 2)}, index=[0]))])

    #cleaning up final columns
    final_df = temp
    final_df = final_df.reset_index(drop=True)
    final_df = final_df.rename(columns={"Value":"Value (kt)"})
    final_df["Item"] = final_df["Item"].replace("Chickens, broilers", "Chickens")
    return [final_df, stock]

if __name__=="__main__":
    app.run(debug=True)
