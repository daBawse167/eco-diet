import os
import random
import difflib
import numpy as np
import pandas as pd
import statistics as stats
from flask import Flask, request, jsonify

app = Flask(__name__)

app.config["SECRET_KEY"] = os.urandom(64)
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = "./.flask_session/"

@app.route("/convert_saved_diet", methods=["GET"])
def convert_saved_diet():
    #get inputs from user
    dish_names = str(request.args.get("dish_names")).split(", ")
    dish_emissions = str(request.args.get("dish_emissions")).split(", ")

    emitting = sum([float(i) for i in dish_emissions])
    
    #break dish names into week
    dish_names_list = []
    
    for dish in dish_names:
        if dish not in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
            dish_names_list.append(dish)

    dish_names_list = [dish_names_list[:3]+["Monday"], dish_names_list[3:6]+["Tuesday"], dish_names_list[6:9]+["Wednesday"], 
               dish_names_list[9:12]+["Thursday"], dish_names_list[12:15]+["Friday"], 
               dish_names_list[15:18]+["Saturday"], dish_names_list[18:21]+["Sunday"]]
    
    dish_emissions = [dish_emissions[:3], dish_emissions[3:6], dish_emissions[6:9], dish_emissions[9:12],
         dish_emissions[12:15], dish_emissions[15:18], dish_emissions[18:21]]

    return {"emitting":emitting, "dish_names":dish_names_list, "dish_emissions":dish_emissions}

@app.route("/reduction_options", methods=["GET"])
def reduction_options():
    emitted = float(request.args.get("emitted"))
    df = pd.read_csv("food-footprints.csv")
    item_emissions = [item["Emissions per kilogram"]*(item["grams"]/1000) for item in df.iloc]
    item_emissions = pd.DataFrame({"emissions":item_emissions}).sort_values(ascending=True, by="emissions")
    item_emissions = list(item_emissions["emissions"])
    
    suitable_list = []

    #loop over reduction options
    for reduction in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
        cumulative = 0
        target = emitted*(1-reduction)

        #loop over meal type
        for type in ["breakfast", "lunch", "dinner"]:

            #get the 7 most emitting dishes
            data = df[df["type"]==type]
            item_emissions = [item["Emissions per kilogram"]*(item["grams"]/1000) for item in data.iloc]
            item_emissions = pd.DataFrame({"emissions":item_emissions}).sort_values(ascending=True, by="emissions")
            item_emissions = list(item_emissions["emissions"])[:7]

            #add to the cumulative total
            for emission in item_emissions:
                cumulative += emission

        #if the emissions have not exceeded the target, add the percentage
        if cumulative <= target:
            suitable_list.append(str(int(reduction*100))+"%")
        else:
            break

    return {"percent_reductions":suitable_list}

@app.route("/calculate_footprint", methods=["GET"])
def calculate_footprint():
    df = pd.read_csv("food-footprints.csv")
    
    input_meals = str(request.args.get("input_meals")).split(", ")
    input_grams = str(request.args.get("input_grams")).split(", ")
    
    emissions_list = []
    
    #calculate the kg CO2 emitted per dish eaten
    i = 0
    for meal in input_meals:
        print(meal)
        kg_eaten = float(input_grams[i])/1000
        kg_emissions = list(df[df["Entity"]==meal]["Emissions per kilogram"])[0]
        emitted = kg_emissions*kg_eaten
        emissions_list.append(emitted)
        i += 1
    
    total_emissions = sum(emissions_list)
    weekly_total_dishes = 14
    
    #adjust the total emissions is the user has not input the entire week
    if len(input_meals) < weekly_total_dishes:
        total_emissions = total_emissions * (weekly_total_dishes/len(input_meals))
        print("total emissions is an estimate")

    #wipe the user_selected dataframe
    selected_dishes = pd.DataFrame({"user_selected_dishes":[], "selected_dishes_position":[]})
    selected_dishes.to_csv("selected_dishes.csv", index=False)
    
    return str(total_emissions)

@app.route("/recommendations", methods=["GET"])
def recommend():

    #get inputs
    footprint = float(request.args.get("footprint"))
    percent_reduction = int(request.args.get("percent_reduction")[:-1])
    selected_dishes = pd.read_csv("selected_dishes.csv")
    
    user_selected_dish = request.args.get("user_selected_dishes")
    selected_dish_position = request.args.get("selected_dishes_position")
    selected_meal_type = request.args.get("meal_type")

    print(selected_dishes)
    print(user_selected_dish)
    print(selected_dish_position)
    print(selected_meal_type)
    
    if user_selected_dish != 'None':
        selected_dishes = selected_dishes._append({"user_selected_dishes":user_selected_dish,
                                                  "selected_dishes_position":selected_dish_position,
                                                  "meal_type":selected_meal_type},
                                                 ignore_index=True)
        selected_dishes.to_csv("selected_dishes.csv", index=False)
    
    user_selected_grams = []
    
    df = pd.read_csv("food-footprints.csv")
    
    target = footprint*(1-(percent_reduction/100))

    recommendation = {"Monday":["", "", ""], "Tuesday":["", "", ""], "Wednesday":["", "", ""], "Thursday":["", "", ""], "Friday":["", "", ""], 
                      "Saturday":["", "", ""], "Sunday":["", "", ""]}
    recommended_emissions = {"Monday":[0, 0, 0], "Tuesday":[0, 0, 0], "Wednesday":[0, 0, 0], "Thursday":[0, 0, 0], "Friday":[0, 0, 0], 
                      "Saturday":[0, 0, 0], "Sunday":[0, 0, 0]}
    
    #loop over all the user-selected meals
    if selected_dishes.isnull().sum().sum() != selected_dishes.shape[0]*selected_dishes.shape[1]:
        selected_dishes = selected_dishes.dropna(how='any',axis=0)
        
        #get the grams of the user_selected_dishes
        selected_dishes = selected_dishes.iloc[1:]
        user_selected_dishes = list(selected_dishes["user_selected_dishes"])
        selected_dishes_position = list(selected_dishes["selected_dishes_position"])
        user_selected_grams = [list(df[df["Entity"]==dish]["grams"])[0] for dish in user_selected_dishes]
        
        idx = 0
        for dish in user_selected_dishes:
            meal_type = list(selected_dishes[selected_dishes["user_selected_dishes"]==dish]["meal_type"])[0]
            
            #randomly insert the meal into a breakfast, lunch or dinner slot
            if meal_type == "breakfast":
                #find the corresponding day of the week
                day = list(recommendation.keys())[int(selected_dishes_position[idx])-1]

                #insert the dish into the result dictionary
                day_dishes = recommendation[day]
                day_dishes[0] = dish
                recommendation[day] = day_dishes

                day_emissions = recommended_emissions[day]
                #calculate the dish's emissions & insert it into the result dictionary
                day_emissions[0] = list(df[df["Entity"]==dish]["Emissions per kilogram"]*(user_selected_grams[idx]/1000))[0]
                recommended_emissions[day] = day_emissions
            elif meal_type == "lunch":
                #find the corresponding day of the week
                day = list(recommendation.keys())[int(selected_dishes_position[idx])-1]

                #insert the dish into the result dictionary
                day_dishes = recommendation[day]
                day_dishes[1] = dish
                recommendation[day] = day_dishes

                day_emissions = recommended_emissions[day]
                #calculate the dish's emissions & insert it into the result dictionary
                day_emissions[1] = list(df[df["Entity"]==dish]["Emissions per kilogram"]*(user_selected_grams[idx]/1000))[0]
                recommended_emissions[day] = day_emissions
            elif meal_type == "dinner":
                #find the corresponding day of the week
                day = list(recommendation.keys())[int(selected_dishes_position[idx])-1]

                #insert the dish into the result dictionary
                day_dishes = recommendation[day]
                day_dishes[2] = dish
                recommendation[day] = day_dishes

                day_emissions = recommended_emissions[day]
                #calculate the dish's emissions & insert it into the result dictionary
                day_emissions[2] = list(df[df["Entity"]==dish]["Emissions per kilogram"]*(user_selected_grams[idx]/1000))[0]
                recommended_emissions[day] = day_emissions

            idx += 1
            
    #set the red meat, white meat and seafood limits
    red_meat_limit = 2
    white_meat_limit = 3
    seafood_limit = 3

    #set the available dish slots for recommendation
    meal_spaces = np.array(list(recommendation.values())).T.tolist()
    meal_spaces = [meal_spaces[0], meal_spaces[1]+meal_spaces[2]]
    meal_type_names = ["breakfast", "meal"]

    print(meal_spaces)
    
    final_dishes = []
    final_emissions = []
    final_meal_type = []
    final_index = []
    chosen_dishes_index = []
    
    i = 0
    idx = 0
    
    #loop over every non-selected meal in the week
    for meal_space in meal_spaces:
        j = 0
    
        #find the highest emitting dishes
        options = df[df["type"]==meal_type_names[i]].sort_values(ascending=False, by="Emissions per kilogram")
        
        for space in meal_space:
    
            #fill the empty spaces with the highest emitters (with the same breakfast, lunch, dinner category)
            if space=="":
                dish_name = list(options["Entity"])[j]
                dish_emissions = list(options["Emissions per kilogram"])[j]*(list(options["grams"])[j]/1000)
                
                final_dishes.append(dish_name)
                final_emissions.append(dish_emissions)
                final_meal_type.append(list(options["type"])[j])
            else:
                #add the user-selected spaces to the resultant array
                item = df[df["Entity"]==space]
                
                final_dishes.append(space)
                final_emissions.append(list(item["Emissions per kilogram"])[0]*(list(item["grams"])[0]/1000))
                final_meal_type.append(list(item["type"])[0])
                chosen_dishes_index.append(idx)
                
            final_index.append(idx)
            j += 1
            idx += 1
        i += 1
    
    current_sum = sum(final_emissions)
    dish_and_emissions = pd.DataFrame({"dish":final_dishes, "emissions":final_emissions, "type":final_meal_type, "index":final_index}).sort_values(ascending=False, by="emissions")
    used_dishes = []
    
    #if the emissions exceed the target
    if current_sum > target:
        break_outer = False
        
        for loop in range(100):
            j = 0
            #track the number of empty options per cycle to see if we need to break
            no_empty = 0
            
            #loop over the highest emitting dishes in order
            for item in dish_and_emissions.iloc:
                options = df[(df["Emissions per kilogram"]*(df["grams"]/1000))<item["emissions"]]
                options = options[options["type"]==item["type"]].sort_values(ascending=False, by="Emissions per kilogram")
                options = pd.DataFrame([i for i in options.iloc if i["Entity"] not in used_dishes])

                if options.empty:
                    no_empty += 1
                
                if not options.empty:
                    choice = options.iloc[0]
                    
                    #replace the dish with a slightly less emitting dish
                    if item["index"] not in chosen_dishes_index:
                        dish_and_emissions.iloc[j] = pd.Series([choice["Entity"], choice["Emissions per kilogram"]*(choice["grams"]/1000), choice["type"], item["index"]])
                        used_dishes.append(choice["Entity"])
                
                #if the target has been reached, break the loop
                if sum(dish_and_emissions["emissions"])<target:
                    break_outer = True
                    break
                j += 1

            if no_empty==len(list(dish_and_emissions.iloc)):
                break_outer = True
            
            if break_outer:
                break
    
    print(dish_and_emissions)
    
    #reshape the data to get into Monday-Sunday format
    total_emitted = sum(dish_and_emissions["emissions"])
    dishes_emissions = dish_and_emissions["emissions"]
    dishes_emissions = [round(float(i), 2) for i in dishes_emissions.iloc]
    
    dish_and_emissions = dish_and_emissions.sort_values(ascending=True, by="index")
    dish_and_emissions = dish_and_emissions.drop(["index"], axis=1)
    
    #dish_and_emissions = [i["dish"]+", "+str(i["emissions"]) for i in dish_and_emissions.iloc]
    dish_and_emissions = dish_and_emissions["dish"]
    dish_and_emissions = pd.DataFrame(dish_and_emissions)
    dish_and_emissions = pd.DataFrame(dish_and_emissions.values.reshape(3, 7))
    
    dish_and_emissions = dish_and_emissions.set_axis(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'], axis=1)
    dish_and_emissions = dish_and_emissions.rename(index={0:'breakfast', 1:'lunch', 2:'dinner'})

    return {"emitted":footprint, "target":total_emitted,
            "recommended": [list(dish_and_emissions["Monday"])+["Monday"], 
            list(dish_and_emissions["Tuesday"])+["Tuesday"], list(dish_and_emissions["Wednesday"])+["Wednesday"], 
            list(dish_and_emissions["Thursday"])+["Thursday"], list(dish_and_emissions["Friday"])+["Friday"], 
            list(dish_and_emissions["Saturday"])+["Saturday"], list(dish_and_emissions["Sunday"])+["Sunday"]],
           "dishes_emissions": list(dishes_emissions)}

#*********************************************** OLD APP BELOW ***********************************************#

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

#convert an array into grams and meat
def array_convert(dishes_eaten_names=[], use_names=True, grams_list=[], meat_list=[]):
    useable = pd.read_csv("useable_dishes.csv")
    eaten = {"chickens":0, "cattle":0, "goats":0, "sheep":0, "swine":0, "buffalo":0}
    dishes = []
    
    if use_names:
        meat = []
        grams = []
        
        for dish in dishes_eaten_names:
            meat.append(list(useable[useable["dish"]==dish]["meat"])[0])
            grams.append(list(useable[useable["dish"]==dish]["grams"])[0])

        dishes = np.array([grams, meat]).T
    else:
        dishes = np.array([grams_list, meat_list]).T
    
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
    
    return eaten

#find closest country and dishes
def country_and_dishes(country_name, input_dishes):
    #converts input country to 
    total_df = pd.read_csv("FAOSTAT.csv")
    countries = np.unique(list(total_df["Area"]))

    #check if the input is inside one of the data points
    country_match = ""
    for country in countries:
        if country_name.lower() in country.lower():
            country_match = country
            country_name = country_match
            break
    #if not, find the closest match
    else:
        country_match = difflib.get_close_matches(country_name, countries, n=1, cutoff=0.1)
        if len(country_match)>0:
            country_match = country_match[0]
            country_name = country_match
    
    #get the data of dishes
    useable = pd.read_csv("useable_dishes.csv")
    target_dishes = list(useable["dish"])
    dishes = []

    #format the inputs to be suitable for the code
    input_dishes = input_dishes.replace('"', "")
    input_dishes = input_dishes.replace("'", "")
    input_dishes = input_dishes.replace('[', "")
    input_dishes = input_dishes.replace(']', "")
    input_dishes = input_dishes.split(",")
    
    #loop over the user's choices
    for dish in input_dishes:
        #get the closest match
        match = difflib.get_close_matches(dish, target_dishes, n=1, cutoff=0.1)
        if len(match)>0:
            match=match[0]
            dishes.append(match)

    return [country_name, dishes]

@app.route("/api_endpoint", methods=["GET"])
def api_diet():
    #input features
    percent_reduction = str(request.args.get("percent_reduction"))

    #make sure no invalid characters are input in the percent_reduction
    if len(percent_reduction) > 2:
        return {"result": "please enter a number between 1-99"}
    for i in percent_reduction:
        if i not in ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]:
            return {"result": "please enter a valid integer"}

    percent_reduction = float(percent_reduction)/100
    
    no_dishes = int(request.args.get("no_dishes"))

    if no_dishes not in range(1, 7):
        return {"result": "please enter a number between 1-6"}
    
    chosen_dishes_meat_input = str(request.args.get("chosen_dishes_meat")).split(", ")
    chosen_dishes_grams = str(request.args.get("chosen_dishes_grams")).split(", ")
    chosen_dishes_names = str(request.args.get("chosen_dishes_names")).split(", ")

    #converts input country to 
    total_df = pd.read_csv("FAOSTAT.csv")
    country_name = str(request.args.get("country_name"))
    
    #user inputs their dishes
    input_dishes = request.args.get("dishes_eaten")

    c_and_d = country_and_dishes(country_name, input_dishes)
    country_name, dishes = c_and_d[0], c_and_d[1]
    
    #incase there is no match, make sure there is no error
    if len(dishes)==0:
        return {"result": "invalid dish input"}
    if country_name=="":
        return {"result": "invalid country input"}

    eaten = array_convert(dishes_eaten_names=dishes, use_names=True)
    recommended = create_recommendations(eaten, country_name, [], percent_reduction,
                                 chosen_dishes_meat_input, chosen_dishes_grams, chosen_dishes_names, no_dishes)

    #combines the recommended dishes with their CO2 production
    dish_emitted = [recommended["recommend_dishes"], recommended["emissions"]]
    #calculates the percentage of CO2 reduced
    percent_reduced = round((recommended["emitted (kg)"]-recommended["target (kg)"])/recommended["emitted (kg)"]*100, 2)
    
    result = {"recommended dishes":list(dish_emitted), "percent reduction":str(percent_reduced)+"%",
              "previously emitted":str(recommended["emitted (kg)"]) + " kg CO2",
              "target emissions":str(recommended["target (kg)"]) + " kg CO2"}
    return result

@app.route("/api_one_dish", methods=["GET"])
def api_one_dish():
    #user inputs their dishes & country
    country_name = str(request.args.get("country_name"))
    input_dish = request.args.get("dish")

    #convert country and dishes to be useable
    c_and_d = country_and_dishes(country_name, input_dish)
    country_name, input_dish = c_and_d[0], c_and_d[1][0]

    #incase there is no match, make sure there is no error
    if len(input_dish)==0:
        return {"result": "invalid dish input"}
    if country_name=="":
        return {"result": "invalid country input"}
    
    #get the meat of the requested dish
    dishes = pd.read_csv("useable_dishes.csv")
    meat = list(dishes[dishes["dish"]==input_dish]["meat"])[0]
    grams = list(dishes[dishes["dish"]==input_dish]["grams"])[0]
    
    df = pd.read_csv("FAOSTAT.csv")
    df = df[df["Area"]==country_name]
    
    df["Item"] = df["Item"].replace("Meat of cattle with the bone, fresh or chilled", "beef")
    df["Item"] = df["Item"].replace("Meat of goat, fresh or chilled", "goat")
    df["Item"] = df["Item"].replace("Meat of buffalo, fresh or chilled", "buffalo")
    df["Item"] = df["Item"].replace("Meat of sheep, fresh or chilled", "lamb")
    df["Item"] = df["Item"].replace("Meat of chickens, fresh or chilled", "chicken")
    df["Item"] = df["Item"].replace("Meat of pig with the bone, fresh or chilled", "pork")
    
    value = df[df["Item"]==meat]["Value"]
    value = round(float(value*(grams/1000)), 3)
    return {f"{input_dish} emissions": str(value)+" kg CO2"}

#user enters in dish type
@app.route("/get_dishes", methods=["GET"])
def get_dishes():

    #dataframe of dishes and their grams&meat
    useable = pd.read_csv("useable_dishes.csv")

    eaten = {"chickens":0, "cattle":0, "goats":0, "sheep":0, "swine":0, "buffalo":0}

    duplicates = useable[useable["dish"].duplicated()]
    for i in duplicates.index:
        useable = useable.drop(i)

    country_name = str(request.args.get("country_name"))
    percent_reduction = float(str(request.args.get("percent_reduction"))[:-1])/100
    favourites = str(request.args.get("favourites")).split(", ")

    #get the specified requested dishes
    chosen_dishes_meat_input = str(request.args.get("chosen_dishes_meat")).split(", ")
    chosen_dishes_grams = str(request.args.get("chosen_dishes_grams")).split(", ")
    chosen_dishes_names = str(request.args.get("chosen_dishes_names")).split(", ")
    no_dishes = int(request.args.get("no_dishes"))
    
    #this route only requires the name of the dishes eaten to be entered
    dishes_eaten_names = request.args.get("dishes_eaten_names")

    eaten = array_convert(dishes_eaten_names=dishes_eaten_names, use_names=dishes_eaten_names is not None, 
                          grams_list=str(request.args.get("grams")).split(", "), 
                          meat_list=str(request.args.get("meat")).split(", "))
    
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
    user_chosen_dishes = []

    print(return_animals)
                               
    if len(chosen_dishes_meat)>0:
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
    
    #keep track of how many red and white dishes are used
    no_red_dishes = 0
    no_white_dishes = 0
    
    portion = 150
    
    red_idx = 0
    white_idx = 0
    
    #make sure we don't break white & red meat's limits
    white_limit = False
    red_limit = False

    #how many grams each dish needs to be
    grams_order = {"Cow":[], "Sheep":[], "Chicken":[], "Pig":[]}
    
    #add the user's pre-selected dishes (if any)
    if len(user_chosen_dishes)>0:
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
                    no_white_dishes += 1
                else:
                    red_meat_counter += meat_emission
                    no_red_dishes += 1
            else:
                user_chosen_dishes = [j for j in user_chosen_dishes if j[2]!=i[2]]
                break
    
    red_meat_options = red_meat_options.sort_values(by="emissions", ascending=False)
    
    #gets the emissions per 1g of each animal
    meat_options = pd.concat([red_meat_options, white_meat_options]).sort_values(by="emissions", ascending=False)

    idx = 0
    
    #get grams and emissions of dishes
    dishes = pd.read_csv("useable_dishes.csv")
    
    for option in meat_options.iloc:
        animal = option["animal"]
        meat_emission = float(option["emissions"])
        
        #make the meat name parsible for the "dishes" dataset
        meat_name = ""
        
        if animal == "Cow":
            meat_name = "beef"
        elif animal == "Sheep":
            meat_name = "lamb"
        elif animal == "Chicken":
            meat_name = "chicken"
        elif animal == "Pig":
            meat_name = "pork"
        
        #find the min amount of 
        dishes = pd.read_csv("useable_dishes.csv")
        unique_grams = np.unique(np.array(dishes[dishes["meat"]==meat_name]["grams"]))

        #to be added to grams_order
        grams_order_list = grams_order[animal]
        
        while emissions_counter+(meat_emission*(100)) < target:
            
            if no_dishes_chosen >= no_dishes:
                break
            #check if the dish satisfies the portion requirement
            elif emissions_counter+(meat_emission*(unique_grams.min())) < target:
                #loop over available gram options: 100g, 150, 200g, 250g
                for grams in unique_grams:
                    if emissions_counter+(meat_emission*grams) < target:
                        emissions_counter += float(meat_emission*grams)
                        recommend_list[animal] += float(grams)
                        no_dishes_chosen += 1
                        grams_order_list.append(grams)
                        #print(recommend_list, emissions_counter, target, grams)
            else:
                #this animal cannot be served, so take it out of the options
                meat_options = meat_options[meat_options["animal"]!=meat_options.iloc[idx]["animal"]]
                break

        grams_order[animal] = grams_order_list
        
        idx += 1

    #print(grams_order)
    
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

    #print(recommend_list)
    
    for food in option_list:

        if len(user_chosen_dishes)>0:
            #add the dish names of the requested dishes
            for i in user_chosen_dishes:
                selection = dishes[dishes["meat"]==food[1]].reset_index(drop=True)
                
                if food[0]==i[0]:
                    
                    choice = selection[selection["dish"]==i[2]]
                    meat_emission = round((animals_eaten[food[0]]*list(choice["grams"])[0])/1000, 3)
                    
                    if sum(dish_emissions)+meat_emission <= target and no_dishes_chosen < no_dishes:
        
                        food[2].append(choice)
                        no_dishes_chosen += 1
        
                        dish_names.append(list(choice["dish"])[0])
                        dish_grams.append(list(choice["grams"])[0])
                        dish_images.append(list(choice["image"])[0])
                        meat_type.append(food[1])
        
                        dish_emissions.append(meat_emission)
        
        #make sure the grams for the meal is correct
        for grams_option in grams_order[food[0]]:
            selection = dishes[dishes["meat"]==food[1]].reset_index(drop=True)
            selection = selection[selection["grams"]==grams_option].reset_index(drop=True)
            #print(food, selection)
            weighting = 4
            goal = 0
        
            #make weighted probabilities for favourite foods
            probabilities = []
            for i in selection.iloc:
                if i["dish"] in favourites:
                    probabilities.append(weighting)
                else:
                    probabilities.append(1)
            
            #loop over all the dishes
            counter = 0
            
            #selection = selection.reset_index(drop=True)
    
            choice = random.choices(list(selection.iloc), probabilities)[0]

            #print(goal, choice, recommend_list[food[0]])
            
            #add the dish
            food[2].append(choice)
            goal += choice["grams"]

            dish_names.append(choice["dish"])
            dish_grams.append(choice["grams"])
            dish_images.append(choice["image"])
            meat_type.append(food[1])

            dish_emissions.append(round((animals_eaten[food[0]]*choice["grams"])/1000, 3))
            #print(dish_emissions, recommend_list[food[0]]-goal, min(list(selection["grams"])))
            
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

    #print(recommend_list)
                               
    return recommend_list



def find_stock(country_name="", eaten={}):
    df = pd.read_csv("meat_per_kg.csv")
    emissions_per_gram_list = []
    weekly_emitted = []
    
    for i in list(df["Entity"]):
        #get the emissions per gram and weekly emitted
        idx = list(df["Entity"]).index(i)
        emissions_per_gram = df["Emissions per kilogram"].iloc[idx] / 1000
        
        emissions_per_gram_list.append(emissions_per_gram)
        weekly_emitted.append(round(emissions_per_gram*eaten[i], 2))
    
    df["emissions (per gram)"] = emissions_per_gram_list
    df["weekly_emitted (kg/animal)"] = weekly_emitted
    
    df.rename(columns = {'Entity':'Item'}, inplace = True)
    df.rename(columns = {'Emissions per kilogram':'emissions (per kg)'}, inplace = True)
    
    return [df, list(df["emissions (per gram)"])]

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
