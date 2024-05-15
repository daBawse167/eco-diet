import os
import random
import numpy as np
import pandas as pd
import statistics as stats
from flask import Flask, request, jsonify

app = Flask(__name__)

app.config["SECRET_KEY"] = os.urandom(64)
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = "./.flask_session/"

@app.route("/meat_footprint", methods=["GET"])
def meat_footprint():
    country = request.args.get("country")
    df = pd.read_csv("FAOSTAT.csv")
    df = df[df["Area"]==country]
    
    return {"beef":list(df[df["Item"]=="Meat of cattle with the bone, fresh or chilled"]["Value"])[0],
        "pork":list(df[df["Item"]=="Meat of pig with the bone, fresh or chilled"]["Value"])[0],
        "lamb":list(df[df["Item"]=="Meat of sheep, fresh or chilled"]["Value"])[0],
        "chicken":list(df[df["Item"]=="Meat of chickens, fresh or chilled"]["Value"])[0]}    

#get the emissions of a single dish
@app.route("/one_dish_emissions", methods=["GET"])
def one_dish_emissions():
    country = request.args.get("country")
    grams = int(request.args.get("grams"))
    meat = request.args.get("meat")
    
    df = pd.read_csv("FAOSTAT.csv")
    df = df[df["Area"]==country]
    
    df["Item"] = df["Item"].replace("Meat of cattle with the bone, fresh or chilled", "beef")
    df["Item"] = df["Item"].replace("Meat of goat, fresh or chilled", "goat")
    df["Item"] = df["Item"].replace("Meat of buffalo, fresh or chilled", "buffalo")
    df["Item"] = df["Item"].replace("Meat of sheep, fresh or chilled", "lamb")
    df["Item"] = df["Item"].replace("Meat of chickens, fresh or chilled", "chicken")
    df["Item"] = df["Item"].replace("Meat of pig with the bone, fresh or chilled", "pork")
    
    value = df[df["Item"]==meat]["Value"]
    value = round(float(value*(grams/1000)), 3)
    return str(value)

#get the link for vegan dish
@app.route("/get_href", methods=["GET"])
def get_href():
    dish = str(request.args.get("dish"))
    df = pd.read_csv("vegan_final.csv")
    return list(df[df["Vegan"]==dish]["href"])[0]

#get most used vegan dishes
@app.route("/most_counted", methods=["GET"])
def most_counted():
    data = pd.read_csv("vegan_final.csv")
    count = [[i[0][0], len(list(i[1].iloc))] for i in data.groupby(["Meat"])]
    count = np.array(count).T
    count = pd.DataFrame({"name":count[0], "count":count[1]})
    count = count.sort_values(by="count", ascending=False)
    return {"name":list(count["name"]), "count":list(count["count"])}

#get vegan alternatives
@app.route("/vegan", methods=["GET"])
def vegan():
    dish = str(request.args.get("dish"))
    df = pd.read_csv("vegan_final.csv")
    result = df[df["Meat"]==dish]
    result = {"Vegan":list(result["Vegan"]), "ingredients":list(result["ingredients"]), "preparation":list(result["preparation"])}
    return result

#user enters in dish type
@app.route("/get_dishes", methods=["GET"])
def get_dishes():
    eaten = {"chickens":0, "cattle":0, "goats":0, "sheep":0, "swine":0, "buffalo":0}
    useable = pd.read_csv("useable_dishes.csv")

    duplicates = useable[useable["dish"].duplicated()]
    for i in duplicates.index:
        useable = useable.drop(i)
    
    country_name = str(request.args.get("country_name"))
    percent_reduction = float(str(request.args.get("percent_reduction"))[:-1])/100
    favourites = str(request.args.get("favourites")).split(", ")
    
    grams = str(request.args.get("grams")).split(", ")
    meat = str(request.args.get("meat")).split(", ")
    dishes = np.array([grams, meat]).T
    
    #convert meat to animal
    for meal in dishes:
        if meal[1]=="beef":
            eaten["cattle"] += float(meal[0])
        elif meal[1]=="pork":
            eaten["swine"] += float(meal[0])
        elif meal[1]=="lamb":
            eaten["sheep"] += float(meal[0])
        elif meal[1]=="chicken":
            eaten["chickens"] += float(meal[0])

    #get the specified requested dishes
    chosen_dishes_meat_input = str(request.args.get("chosen_dishes_meat")).split(", ")
    chosen_dishes_grams = str(request.args.get("chosen_dishes_grams")).split(", ")
    chosen_dishes_names = str(request.args.get("chosen_dishes_names")).split(", ")
    no_dishes = int(request.args.get("no_dishes"))
    
    return create_recommendations(eaten, country_name, favourites, percent_reduction,
                                 chosen_dishes_meat_input, chosen_dishes_grams, chosen_dishes_names, no_dishes)

#user enters in grams
@app.route("/get_grams", methods=["GET"])
def get_grams():
    country_name = str(request.args.get("country_name"))
    
    chickens = int(request.args.get("chickens"))
    cattle = int(request.args.get("cattle"))
    goats = int(request.args.get("goats"))
    sheep = int(request.args.get("sheep"))
    swine = int(request.args.get("swine"))
    buffalo = int(request.args.get("buffalo"))

    eaten = {"chickens":chickens, "cattle":cattle, "goats":goats, "sheep":sheep, "swine":swine, "buffalo":buffalo}
    return create_recommendations(eaten, country_name)

def create_recommendations(eaten, country_name, favourites, percent_reduction,
                           chosen_dishes_meat_input, chosen_dishes_grams, chosen_dishes_names, no_dishes):
    
    chickens = eaten["chickens"]
    cattle = eaten["cattle"]
    goats = eaten["goats"]
    sheep = eaten["sheep"]
    swine = eaten["swine"]
    buffalo = eaten["buffalo"]
    
    chosen_dishes_meat = []
    #make the requested meat parseable for later on
    for i in chosen_dishes_meat_input:
        if i=="beef":
            chosen_dishes_meat.append("Cow")
        elif i=="pork":
            chosen_dishes_meat.append("Pig")
        elif i=="chicken":
            chosen_dishes_meat.append("Chicken")
        elif i=="lamb":
            chosen_dishes_meat.append("Sheep")
    
    eaten = {'Chicken':chickens, 'Buffalo':buffalo,
             'Cow':cattle, 'Goat':goats, 'Sheep':sheep, 'Pig':swine}

    no_dishes_chosen=0
    
    return_animals = find_stock(country_name=country_name, eaten=eaten)
    animals_eaten, options = return_animals[0], return_animals[1]


    user_chosen_dishes = np.array([chosen_dishes_meat, chosen_dishes_grams, chosen_dishes_names]).T

    if len(user_chosen_dishes)>0:
        #get the emissions of the user chosen dishes animals
        user_chosen_emissions = [list(animals_eaten["emissions (per gram)"])[list(animals_eaten["Item"]).index(i)] for i in list(user_chosen_dishes.T)[0]]
        #sort the dishes by emissions
        user_chosen_dishes = pd.DataFrame({"animal":list(user_chosen_dishes.T)[0], "grams":list(user_chosen_dishes.T)[1],
                                          "dishes":list(user_chosen_dishes.T)[2], "emissions":user_chosen_emissions}).sort_values(by="emissions", ascending=False)
        user_chosen_dishes = np.array([user_chosen_dishes["animal"], user_chosen_dishes["grams"], user_chosen_dishes["dishes"]]).T

                               
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
    red_meat = ['Cow', 'Sheep', 'Pig']
    
    
    
    white_meat_options_list = [i for i in low_carbon if i[0] in white_meat]
    red_meat_options_list = [i for i in low_carbon if i[0] in red_meat]
    
    red_meat_options = {"animal":[], "emissions":[]}
    white_meat_options = {"animal":[], "emissions":[]}
    
    if len(red_meat_options) > 0:
        red_meat_options = {"animal": np.array(red_meat_options_list).T[0], "emissions": np.array(red_meat_options_list).T[1]}
        red_meat_options = pd.DataFrame(red_meat_options).sample(frac=1)#.sort_values(ascending=True, by="emissions")
    if len(white_meat_options) > 0:
        white_meat_options = {"animal": np.array(white_meat_options_list).T[0], "emissions": np.array(white_meat_options_list).T[1]}
        white_meat_options = pd.DataFrame(white_meat_options).sample(frac=1)#.sort_values(ascending=True, by="emissions")
    
    idx = 0
    recommend_list = {"emitted (kg)":round(total_emitted, 3),
                      "target (kg)":0,
                     'Chicken': 0,
                     'Cow': 0,
                     'Sheep': 0,
                     'Pig': 0}
    emissions_counter = 0
    white_meat_counter = 0
    red_meat_counter = 0
    
    portion = 150
    
    red_idx = 0
    white_idx = 0
    
    #make sure we don't break white & red meat's limits
    white_limit = False
    red_limit = False
    
    #add the user's pre-selected dishes (if any)
    for i in user_chosen_dishes:
        meat=i[0]
        grams=i[1]
    
        #gets the emissions per 1g of each animal
        meat_options = pd.concat([white_meat_options, red_meat_options])
        
        #calculates hypothetical emissions of each "chosen dish"
        meat_emission = float(list(meat_options[meat_options["animal"]==meat]["emissions"])[0])
        meat_emission = meat_emission*float(grams)
    
        #add the meat emissions to the emissions counters
        if emissions_counter+meat_emission <= target and no_dishes_chosen < no_dishes:
            emissions_counter += meat_emission
            recommend_list[meat] += float(grams)
            no_dishes_chosen += 1
    
            if meat=="Chicken":
                white_meat_counter += meat_emission
            else:
                red_meat_counter += meat_emission
        else:
            user_chosen_dishes = [j for j in user_chosen_dishes if j[2]!=i[2]]
            break

    #gets the emissions per 1g of each animal
    meat_options = pd.concat([red_meat_options, white_meat_options]).sort_values(by="emissions", ascending=False)
    idx = 0

    #loop over the meat-types
    for option in meat_options.iloc:
        animal = option["animal"]
        meat_emission = float(option["emissions"])
        
        while emissions_counter+(meat_emission*(portion*(2/3))) < target:
            
            if no_dishes_chosen >= no_dishes:
                break
            #check if the dish satisfies the portion requirement
            elif emissions_counter+(meat_emission*portion) < target:
                emissions_counter += meat_emission*portion
                recommend_list[animal] += portion
                no_dishes_chosen += 1
                print(recommend_list, emissions_counter, target)
            #if not, check a smaller portion
            elif emissions_counter+(meat_emission*(portion*(2/3))) < target:
                new_portion = portion*(2/3)
                emissions_counter += meat_emission*new_portion
                recommend_list[animal] += new_portion
                no_dishes_chosen += 1
                print(recommend_list, emissions_counter, target)
            else:
                #this animal cannot be served, so take it out of the options
                meat_options = meat_options[meat_options["animal"]!=meat_options.iloc[idx]["animal"]]
        
        idx += 1
    
    """red_meat_options = red_meat_options.sort_values(by="emissions", ascending=False)
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
                
        print(red_meat_options, recommend_list, no_dishes_chosen)

        break_ = False

        #add two red meats before one white meat
        for j in range(2):
            if len(list(red_meat_options.iloc)) > 0:
                #add 1 portion of red meat & its emissions
                meat_emission = float(red_meat_options.iloc[red_idx]["emissions"])
                animal = red_meat_options.iloc[red_idx]["animal"]
                
                #make sure we don't add too many dishes
                if no_dishes_chosen >= no_dishes:
                    break_ = True
                #check if the dish satisfies the portion requirement
                elif emissions_counter+(meat_emission*portion) < target:
                    emissions_counter += meat_emission*portion
                    red_meat_counter += portion
                    recommend_list[animal] += portion
                    no_dishes_chosen += 1
                #if not, check a smaller portion
                elif emissions_counter+(meat_emission*(portion*(2/3))) < target:
                    new_portion = portion*(2/3)
                    emissions_counter += meat_emission*new_portion
                    red_meat_counter += new_portion
                    recommend_list[animal] += new_portion
                    no_dishes_chosen += 1
                else:
                    #this animal cannot be served, so take it out of the options
                    red_meat_options = red_meat_options[red_meat_options["animal"]!=red_meat_options.iloc[red_idx]["animal"]]
                print(recommend_list, no_dishes_chosen, "red", round(emissions_counter+(meat_emission*portion), 2), round(target, 2))
            else:
                red_limit = True
        
        if len(list(white_meat_options.iloc)) > 0:
            #add 1 portion of white meat & its emissions
            meat_emission = float(white_meat_options.iloc[white_idx]["emissions"])
            animal = white_meat_options.iloc[white_idx]["animal"]
    
            if emissions_counter+(meat_emission*portion) < target and no_dishes_chosen < no_dishes:
                emissions_counter += meat_emission*portion
                white_meat_counter += portion
                recommend_list[animal] += portion
                no_dishes_chosen += 1
            else:
                #this animal cannot be served, so take it out of the options
                white_meat_options = white_meat_options[white_meat_options["animal"]!=white_meat_options.iloc[white_idx]["animal"]]
            print(recommend_list, no_dishes_chosen, "white", round(emissions_counter+(meat_emission*portion), 2), round(target, 2))
            
        else:
            white_limit = True
    
        red_idx += 1
        white_idx += 1

        #breaks if the number of dishes exceeds
        if break_:
            break"""
    
    #bring in the dishes here
    dishes = pd.read_csv("useable_dishes.csv")
    
    beef_options = []
    pork_options = []
    chicken_options = []
    lamb_options = []
    
    #show the emissions of ALL animals
    animals_eaten.index=animals_eaten["Item"]
    animals_eaten = animals_eaten["emissions (per kg)"]
    
    option_list = [["Cow", "beef", beef_options], ["Sheep", "lamb", lamb_options], 
                  ["Pig", "pork", pork_options], ["Chicken", "chicken", chicken_options]]
    
    dish_names = []
    dish_grams = []
    dish_images = []
    dish_emissions = []
    meat_type = []

    no_dishes_chosen = 0
    
    for food in option_list:
    
        selection = dishes[dishes["meat"]==food[1]].reset_index(drop=True)
        weighting = 4
        goal = 0
    
        #add the dish names of the requested dishes
        for i in user_chosen_dishes:
    
            if food[0]==i[0]:
                
                choice = selection[selection["dish"]==i[2]]
                meat_emission = round((animals_eaten[food[0]]*list(choice["grams"])[0])/1000, 3)
                
                print(no_dishes_chosen)
                
                if sum(dish_emissions)+meat_emission <= target and no_dishes_chosen < no_dishes:
    
                    food[2].append(choice)
                    goal += list(choice["grams"])[0]
                    no_dishes_chosen += 1
    
                    dish_names.append(list(choice["dish"])[0])
                    dish_grams.append(list(choice["grams"])[0])
                    dish_images.append(list(choice["image"])[0])
                    meat_type.append(food[1])
    
                    dish_emissions.append(meat_emission)
    
        #make weighted probabilities for favourite foods
        probabilities = []
        for i in selection.iloc:
            if i["dish"] in favourites:
                probabilities.append(weighting)
            else:
                probabilities.append(1)
    
        #loop over all the dishes
        counter = 0
        while goal < recommend_list[food[0]]:
            selection = selection.reset_index(drop=True)
    
            choice = random.choices(list(selection.iloc), probabilities)[0]
    
            #get the index of selection so you can remove the weighting
            idx = selection[selection["Unnamed: 0"]==choice["Unnamed: 0"]].index[0]
            #del probabilities[idx]
            #selection = selection[selection["Unnamed: 0"]!=choice["Unnamed: 0"]]
    
            #if we haven't reached the limit yet
            if goal+choice["grams"] <= recommend_list[food[0]]:
                #add the dish
                food[2].append(choice)
                goal += choice["grams"]
    
                dish_names.append(choice["dish"])
                dish_grams.append(choice["grams"])
                dish_images.append(choice["image"])
                meat_type.append(food[1])
    
                dish_emissions.append(round((animals_eaten[food[0]]*choice["grams"])/1000, 3))
    
            if (recommend_list[food[0]]-goal) < min(list(selection["grams"])):
                break
    
            #if counter>len(list(selection.iloc)):
             #   break
            counter += 1
    
    #join dish name and its grams
    recommend_list["recommend_dishes"] = [dish[0]+" ("+dish[1]+"g "+dish[2]+")   " for dish in np.array([dish_names, dish_grams, meat_type]).T]
    recommend_list["target (kg)"] = sum(dish_emissions)
    recommend_list["image"] = dish_images
    recommend_list["emissions"] = dish_emissions

    print(recommend_list)
                               
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

@app.route('/present', methods=["GET"])
def present():
    country = request.args.get("country_name")
    
    total_df = pd.read_csv("FAOSTAT.csv")
    country_df = total_df[total_df["Area"]==country]
    
    country_df["Item"] = country_df["Item"].replace("Meat of cattle with the bone, fresh or chilled", "Cow")
    country_df["Item"] = country_df["Item"].replace("Meat of goat, fresh or chilled", "Goat")
    country_df["Item"] = country_df["Item"].replace("Meat of buffalo, fresh or chilled", "Buffalo")
    country_df["Item"] = country_df["Item"].replace("Meat of sheep, fresh or chilled", "Sheep")
    country_df["Item"] = country_df["Item"].replace("Meat of chickens, fresh or chilled", "Chicken")
    country_df["Item"] = country_df["Item"].replace("Meat of pig with the bone, fresh or chilled", "Pig")
    
    animals = list(np.unique(country_df[country_df["Area"]==country]["Item"]))
    present = []
    emissions = []
    
    for animal in ['Buffalo', 'Chicken', 'Cow', 'Goat', 'Pig', 'Sheep']:
        present.append(animal in animals)
        if animal in animals:
            idx = list(country_df["Item"]).index(animal)
            emissions.append(round(list(country_df["Value"])[idx], 2))
        else:
            emissions.append(0)
    
    return {'Buffalo':present[0], 'Chicken':present[1], 'Cow':present[2], 'Goat':present[3], 'Pig':present[4], 'Sheep':present[5],
     
        "buffalo_e":emissions[0], "chicken_e":emissions[1], "cow_e":emissions[2], "goat_e":emissions[3], "pig_e":emissions[4], 
     "sheep_e":emissions[5]}

if __name__=="__main__":
    app.run(debug=True)
