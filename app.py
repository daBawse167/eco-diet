import os
import random
import difflib
import numpy as np
import pandas as pd
import statistics as stats
from mixpanel import Mixpanel
from flask import Flask, request, jsonify

mp = Mixpanel("d4b693c5d364e3b373a9ba71b330bf1b")

app = Flask(__name__)

app.config["SECRET_KEY"] = os.urandom(64)
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = "./.flask_session/"

@app.route("/input_meal", methods=["GET"])
def input_meal():
    user_id = request.args.get("user_id")
    mp.track(user_id, "Input meal")
    return {"user_id":user_id}

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
    mp.track("a", "Calculating Footprint")
    
    df = pd.read_csv("food-footprints.csv")
    
    input_meals = str(request.args.get("input_meals")).split(", ")
    input_grams = str(request.args.get("input_grams")).split(", ")
    no_dishes = str(request.args.get("no_dishes")).split(", ")
    
    emissions_list = []
    no_dishes = [int(i) for i in no_dishes]
    
    #calculate the kg CO2 emitted per dish eaten
    i = 0
    for meal in input_meals:
        print(meal, input_grams[i], no_dishes[i])
        kg_eaten = float(float(input_grams[i])*float(no_dishes[i]))/1000
        kg_emissions = list(df[df["Entity"]==meal]["Emissions per kilogram"])[0]
        print(kg_eaten, kg_emissions)
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
