import os
import numpy as np
import pandas as pd
import statistics as stats
from flask import Flask, request, jsonify

app = Flask(__name__)

app.config["SECRET_KEY"] = os.urandom(64)
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = "./.flask_session/"


total_df = pd.read_csv("livestock.csv")

#get the average mass of each animal
df = pd.read_csv("average_mass.csv", encoding="latin")
#structure dataset
data = pd.DataFrame([i.split(",") for i in df["feature"].iloc], columns=["country", "Cattle", "Swine", "Sheep", "Goats",
                                                                         "Chickens", "Turkeys", "Ducks"])
data = data[["country", "Cattle", "Swine", "Sheep", "Goats", "Chickens", "Turkeys", "Ducks"]]
#remove null
data["Turkeys"] = data["Turkeys"].replace("N/A", "7-9")
data["Ducks"] = data["Ducks"].replace("N/A", "3-4")

#find the average of the mean range
array = []
for i in data.iloc:
    subarray = []
    subarray.append(list(i)[0])
    for j in list(i)[1:]:
        subarray.append(stats.mean([float(j.split("-")[0]), float(j.split("-")[1])]))
    array.append(subarray)

#find the percentage usable mass of each animal
data = pd.DataFrame(array, columns=["country", "Cattle", "Swine", "Sheep", "Goats", "Chickens", "Turkeys", "Ducks"])
usable_meat = pd.DataFrame({"Cattle":[0.45], "Swine":[0.575], "Sheep":[0.5], "Goats":[0.5], "Chickens":[0.725],
                            "Turkeys":[0.725], "Ducks":[0.65]})


@app.route("/recommend", methods=["GET"])
def create_recommendations():
    country_name = str(request.args.get("country_name"))
    print(country_name)
    
    chickens = int(request.args.get("chickens")[:-1])
    ducks = int(request.args.get("ducks")[:-1])
    turkeys = int(request.args.get("turkeys")[:-1])
    cattle = int(request.args.get("cattle")[:-1])
    goats = int(request.args.get("goats")[:-1])
    sheep = int(request.args.get("sheep")[:-1])
    swine = int(request.args.get("swine")[:-1])

    eaten = {'Chickens':chickens, 'Ducks':ducks, 'Turkeys':turkeys,
             'Cattle':cattle, 'Goats':goats, 'Sheep':sheep, 'Swine':swine}
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
            low_carbon.append([animals_eaten["Item"][i], option])
        i += 1
        
    #in case no choice is made, get the min red and white meat animals
    white_meat = ['Chickens', 'Ducks', 'Turkeys']
    red_meat = ['Cattle', 'Goats', 'Sheep', 'Swine']
    
    white_meat_options = [i for i in low_carbon if i[0] in white_meat]
    red_meat_options = [i for i in low_carbon if i[0] in red_meat]
        
    idx = 0
    recommend_list = {"emitted (kg)":round(total_emitted, 3),
                      "target (kg)":0,
                     'Chickens': 0,
                     'Ducks': 0,
                     'Turkeys': 0,
                     'Cattle': 0,
                     'Goats': 0,
                     'Sheep': 0,
                     'Swine': 0}
    emissions_counter = 0
    white_meat_counter = 0
    red_meat_counter = 0
    
    white_meat_max = 340
    red_meat_max = 500
    
    #check if we have any options
    if len(white_meat_options) > 0 or len(red_meat_options) > 0:
        break_outer_loop = False
        
        while emissions_counter < target:
            
            if break_outer_loop:
                break
            
            #don't add too much white meat
            if white_meat_counter < white_meat_max:
                
                #add white meats twice
                j = 0
                for i in white_meat_options:
                    if j < 2 and white_meat_counter<white_meat_max:
                        
                        #make sure we're not adding on too many emissions
                        if (emissions_counter+i[1]) < target:
                            #i[0] = name of animal
                            recommend_list[i[0]]+=1
                            white_meat_counter += 1
                            emissions_counter += i[1]
                            j += 1
                        else:
                            break_outer_loop = True
                            break
                    else:
                        break
            else:
                break

            #check if there's any red meat with a low enough emissions
            if len(red_meat_options) > 0:
                #don't add too much red meat
                if red_meat_counter < red_meat_max:
                    #add one red meat
                    if idx==3:
                        idx=0

                    #make sure we're not adding on too many emissions
                    if (emissions_counter+red_meat_options[idx][1])<target:
                        #red_meat_options[idx][0] = name of animal
                        recommend_list[red_meat_options[idx][0]] += 1
                        emissions_counter += red_meat_options[idx][1]
                        red_meat_counter += 1
                        idx += 1
                    else:
                        break
                else:
                    break
    
    recommend_list["target (kg)"] = round(emissions_counter, 3)
    
    #show the emissions of ALL animals
    animals_eaten.index=animals_eaten["Item"]
    animals_eaten = animals_eaten["emissions (per kg)"]
    
    #present each animal's recommended emissions
    animals_e = {"Cattle":0, "Chickens":0, "Ducks":0, "Goats":0, "Sheep":0, "Swine":0, "Turkeys":0}
    
    for i in animals_eaten.index:
        animals_e[i] = round(animals_eaten.loc[i]*(recommend_list[i]/1000), 3)
        
    #fills in animals not listed in country
    for idx in white_meat+red_meat:
        if idx not in list(animals_e.keys()):
            animals_e[idx] = 0
    
    #adds emissions to output dictionary
    recommend_list["cattle_e"] = animals_e["Cattle"]
    recommend_list["chickens_e"] = animals_e["Chickens"]
    recommend_list["ducks_e"] = animals_e["Ducks"]
    recommend_list["goats_e"] = animals_e["Goats"]
    recommend_list["sheep_e"] = animals_e["Sheep"]
    recommend_list["swine_e"] = animals_e["Swine"]
    recommend_list["turkeys_e"] = animals_e["Turkeys"]
    
    return recommend_list



def find_stock(country_name="", eaten={}):
    #finds stocks for cattle and swine
    cleaned_data = clean_data()
    final_df, stock = cleaned_data[0], cleaned_data[1]

    country_df = final_df[final_df["Area"]==country_name]
    country_stocks = stock[stock["Area"]==country_name]
    cattle_stocks = sum(country_stocks[stock["Item"]=="Cattle"]["Value"])
    swine_stocks = sum(country_stocks[stock["Item"]=="Swine"]["Value"])

    #database storing impact of eaten meat
    no_eaten = []
    value_list = []
    stock_list = []
    per_capita = []
    
    for i in country_df["Item"]:
        idx = list(country_df["Item"]).index(i)

        #finds stocks for the animals
        if i != "Cattle":
            if i != "Swine":
                stock_list.append(list(country_stocks[country_stocks["Item"]==i]["Value"])[0])
            else:
                stock_list.append(swine_stocks)
        else:
            stock_list.append(cattle_stocks)

        no_eaten.append(eaten[i])
        value_list.append(country_df.iloc[idx]["Value (kt)"]*1000000)

        #calculates the emissions of animal per person and weekly
        per_capita.append(value_list[idx]/stock_list[idx])
        #total_value.append(per_capita[idx]*eaten[i])

    country_avg_mass = data[data["country"]==country_name]
    animals_avg_mass = [list(country_avg_mass[i])[0] for i in list(country_df["Item"])]
    
    #calculate how much mass in an animal is usable
    usable_meats = []
    emissions_per_kg_list = []
    emissions_per_gram_list = []
    weekly_emitted = []
    
    for i in list(country_df["Item"]):
        idx = list(country_df["Item"]).index(i)
        
        #get the percentage of usable meat
        usable = list(usable_meat[i])[0]
        #get the average mass
        avg_mass = list(country_avg_mass[i])[0]
        #calculate out how much mass is used
        usable_mass = usable*avg_mass
        usable_meats.append(usable_mass)
        
        #find the emissions of one of the animal
        one_animal_emissions = per_capita[idx]
        #calculate emissions per kg of the animal
        emissions_per_kg = one_animal_emissions/usable_mass
        emissions_per_gram = emissions_per_kg/1000
        
        emissions_per_kg_list.append(emissions_per_kg)
        emissions_per_gram_list.append(emissions_per_gram)
        
        #find the weekly emissions per animal, given the user's input in grams
        weekly_emitted.append(emissions_per_gram*eaten[i])
    
    #puts it all together in one databse
    animals_eaten = pd.DataFrame({"Item":list(country_df["Item"]), "no. eaten":no_eaten, "Value (kg)":value_list,
                                  "stock":stock_list, "per capita (GHG kg/animal)":per_capita,
                                  "average_mass (kg)":animals_avg_mass, "usable_meat (animal kg)":usable_meats,
                                  "emissions (per kg)":emissions_per_kg_list, "emissions (per gram)":emissions_per_gram_list,
                                  "weekly_emitted (kg/animal)":weekly_emitted})
    
    options = list(animals_eaten["emissions (per gram)"])
    return [animals_eaten, options]



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
