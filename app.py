import os
import numpy as np
import pandas as pd
from flask import Flask, request, jsonify

total_df = pd.read_csv("livestock.csv")

app = Flask(__name__)

app.config["SECRET_KEY"] = os.urandom(64)
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = "./.flask_session/"

@app.route("/recommend", methods=["GET"])
def create_recommendations():
    country_name = str(request.args.get("country_name"))
    print(country_name)
    
    chickens = int(request.args.get("chickens"))
    ducks = int(request.args.get("ducks"))
    turkeys = int(request.args.get("turkeys"))
    cattle = int(request.args.get("cattle"))
    goats = int(request.args.get("goats"))
    sheep = int(request.args.get("sheep"))
    swine = int(request.args.get("swine"))

    eaten = {'Chickens':chickens, 'Ducks':ducks, 'Turkeys':turkeys,
             'Cattle':cattle, 'Goats':goats, 'Sheep':sheep, 'Swine':swine}
    percent_reduction = 0.5
    
    return_animals = find_stock(country_name=country_name, eaten=eaten)
    animals_eaten, options = return_animals[0], return_animals[1]
    
    #find the target emissions
    total_emitted = sum(animals_eaten["weekly_emitted (* 10^6)"])
    target = (1-percent_reduction)*total_emitted
    
    low_carbon = []
    i = 0
    #gets the animals with GHG lower than the target
    for option in options:
        if option <= target:
            low_carbon.append([animals_eaten["Item"][i], option])
        i += 1
        
    #split white and red meats
    white_meat = ['Chickens', 'Ducks', 'Turkeys']
    red_meat = ['Cattle', 'Goats', 'Sheep', 'Swine']
    
    white_meat_options = [i for i in low_carbon if i[0] in white_meat]
    red_meat_options = [i for i in low_carbon if i[0] in red_meat]
        
    idx = 0
    recommend_list = {"emitted":round(total_emitted),
                      "target":0,
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
    
    #check if we have any options
    if len(white_meat_options) > 0 or len(red_meat_options) > 0:
        break_outer_loop = False
        
        while emissions_counter < target:

            if break_outer_loop:
                break
            
            #don't add too much white meat
            if white_meat_counter < 4:
                
                #add two white meat
                j = 0
                for i in white_meat_options:
                    if j < 2 and white_meat_counter<4:
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
                if red_meat_counter < 2:
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
    
    recommend_list["target"] = round(emissions_counter)
    return jsonify(recommend_list)



def find_stock(country_name, eaten):
    #finds stocks for cattle and swine
    cleaned_data = clean_data()
    final_df, stock = cleaned_data[0], cleaned_data[1]

    country_df = final_df[final_df["Area"]==country_name]
    country_stocks = stock[stock["Area"]==country_name]
    cattle_stocks = sum(country_stocks[stock["Item"]=="Cattle"]["Value"])
    swine_stocks = sum(country_stocks[stock["Item"]=="Swine"]["Value"])

    #database storing impact of eaten meat
    no_eaten = []
    total_value = []
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
        value_list.append(country_df.iloc[idx]["Value (kt)"])

        #calculates the emissions of animal per person and weekly
        per_capita.append((value_list[idx]*(10**6))/stock_list[idx])
        total_value.append(per_capita[idx]*eaten[i])

    #puts it all together in one databse
    animals_eaten = pd.DataFrame({"Item":list(country_df["Item"]), "no. eaten":no_eaten, "Value (kt)":value_list,
                                  "stock":stock_list, "per capita (* 10^6)":per_capita, "weekly_emitted (* 10^6)":total_value})

    options = list(animals_eaten["per capita (* 10^6)"])
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
