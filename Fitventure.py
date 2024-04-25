from flask import Flask, jsonify, render_template, request, redirect, url_for
from pymongo import MongoClient
import json
from flask_login import LoginManager, UserMixin, current_user, login_user, logout_user, login_required
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
import bcrypt
import os

app = Flask(__name__, static_folder='static')
app.config['SECRET_KEY'] = os.urandom(24)

login_manager = LoginManager()
login_manager.init_app(app)

class User(UserMixin):
    def __init__(self, user_id, **kwargs):
        self.id = user_id
        self.username = kwargs.get('username', '')
        self.password = kwargs.get('password', '')

    def get_id(self):
        return self.id

@login_manager.user_loader
def load_user(user_id):
    user_data = users_collections.find_one({'_id': ObjectId(user_id)})
    if user_data:
        return User(user_id=str(user_data['_id']), username=user_data['username'])
    return None


client = MongoClient('mongodb://localhost:27017')
db = client.fitventure
users_collections = db['users']
recipes_collections = db['recipes']
exercise_collections = db['exercise_locations']
reviews_collections = db['reviews']
favourites_collections = db['favourites']

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(stored_password, provided_password):
    return bcrypt.checkpw(provided_password.encode('utf-8'), stored_password.encode('utf-8'))


# Check if collections are empty
if users_collections.count_documents({}) == 0:
    with open('data.json', 'r') as file:
        data = json.load(file)

    # Insert data into collections
    users_collections.insert_many(data['users'])
    recipes_collections.insert_many(data['recipes'])
    exercise_collections.insert_many(data['exercise_locations'])
    reviews_collections.insert_many(data['reviews'])
    favourites_collections.insert_many(data['favourites'])

#register page 
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Handle form data
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # Check for missing fields
        if not username or not email or not password or not confirm_password:
            return jsonify(message='All fields are required'), 400

        # Check if passwords match
        if password != confirm_password:
            return jsonify(message='Passwords do not match'), 400

        # Check if username or email already exists
        if users_collections.find_one({'$or': [{'username': username}, {'email': email}]}):
            return jsonify(message='Username or email already exists'), 400

        # Hash the password
        hashed_password = hash_password(password)

        # Insert user into database
        user_id = users_collections.insert_one({'username': username, 'password': hashed_password, 'email': email}).inserted_id

        # Redirect to homepage or login page after successful registration
        return redirect(url_for('index'))  

    else:
        # Render the registration form
        return render_template('register.html')



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Check the content type of the request
        if request.content_type == 'application/json':
            # Handle JSON data
            data = request.json
            username = data.get('username')
            password = data.get('password')
        else:
            # Handle form data
            username = request.form.get('username')
            password = request.form.get('password')

        if not username or not password:
            return jsonify(message='Username and password are required'), 400

        user = users_collections.find_one({'username': username})
        if user and check_password(user['password'], password):
            user_obj = User(user_id=str(user['_id']), username=user['username'], password=user['password'])
            login_user(user_obj)
            return redirect('/')
        else:
            return jsonify(message='Invalid credentials'), 401
    else:
        # Render the login form
        return render_template('login.html')



@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'GET':
        return render_template('reset_password.html')
    
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        new_password = data.get('new_password')

        if not username or not new_password:
            return jsonify(message='Username and new password are required'), 400

        # Assuming you have a MongoDB setup similar to your previous example
        user = users_collections.find_one({'username': username})
        if not user:
            return jsonify(message='User not found'), 404

        hashed_password = hash_password(new_password)
        users_collections.update_one({'_id': user['_id']}, {'$set': {'password': hashed_password}})
        
        return redirect(url_for('login'))


@app.route('/logout', methods=['POST'])
def logout():
    if current_user.is_authenticated:
        logout_user()
    return redirect(url_for('index'))



# Homepage route
@app.route('/')
def index():
    exercise_locations = list(exercise_collections.find())  # Fetch exercise locations from MongoDB
    
    # Check if 'image' key exists for each location
    exercise_locations_with_images = [location for location in exercise_locations if 'image' in location]
    
    print("Exercise Location Image paths:", [location['image'] for location in exercise_locations_with_images])
    
    return render_template('index.html', exercise_locations=exercise_locations_with_images)



# Search bar 
@app.route('/search')
def search():
    query = request.args.get('query')
    return redirect(url_for('country_details', country_name=query))

# Recipes page

@app.route('/recipes')
def recipes_page():
    # Render the template with the list of countries
    return render_template('countries.html')

@app.route('/country/<country_name>')
def country_details(country_name):
    # Get recipes for the selected country
    recipes = list(recipes_collections.find({'Country': country_name}))
    
    # Get exercise locations for the selected country
    exercise_locations = list(exercise_collections.find({'country': country_name}))
    
    # Retrieve reviews for the recipes
    review_ids = [recipe['id'] for recipe in recipes]  # Get the ids from recipes
    reviews = list(reviews_collections.find({'recipe_id': {'$in': review_ids}}))
    
    # Convert review recipe_id to string for matching with recipes
    for review in reviews:
        review['recipe_id'] = str(review['recipe_id'])

    # Fetch usernames for each review
    user_ids = [review['user_id'] for review in reviews]
    users = {user['id']: user['Username'] for user in users_collections.find({'id': {'$in': user_ids}})}

    # Update reviews to include usernames
    for review in reviews:
        review['username'] = users.get(review['user_id'], 'Unknown User')

    return render_template('country_details.html', country=country_name, recipes=recipes, exercise_locations=exercise_locations, reviews=reviews)




#add review
@app.route('/add_review', methods=['POST'])
@login_required
def add_review():
    data = request.get_json()
    current_user_id = current_user.id  # using Flask-Login's current_user
    recipe_id = data.get('recipe_id')
    review_text = data.get('review_text')
    rating = data.get('rating')

    if not all([recipe_id, review_text, rating]):
        return jsonify(message='Missing required data'), 400

    review = {
        'user_id': current_user_id,
        'recipe_id': ObjectId(recipe_id),
        'review_text': review_text,
        'rating': rating
    }
    new_review = reviews_collections.insert_one(review)

    return jsonify({
        '_id': str(new_review.inserted_id),
        'user_id': current_user_id,
        'recipe_id': str(review['recipe_id']),
        'review_text': review['review_text'],
        'rating': review['rating']
    }), 200

@app.route('/reviews', methods=['GET', 'POST'])
@app.route('/reviews/<review_id>', methods=['GET', 'POST', 'DELETE'])
def reviews(review_id=None):
    if request.method == 'GET':
        if review_id:
            review = reviews_collections.find_one({'_id': review_id})
            return render_template('edit_review.html', review=review)
        else:
            current_user_reviews = reviews_collections.find({'user_id': current_user.id})
            return render_template('reviews.html', reviews=current_user_reviews)

    elif request.method == 'POST':
        if review_id:
            updated_content = request.form.get('content')
            reviews_collections.update_one({'_id': review_id}, {'$set': {'content': updated_content}})
        else:
            email = request.form.get('email')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            # Reset password logic here
        return redirect(url_for('reviews'))

    elif request.method == 'DELETE':
        reviews_collections.delete_one({'_id': review_id})
        return redirect(url_for('reviews'))


@app.route('/add_to_favourites', methods=['POST'])
@login_required
def add_to_favourites():
    current_user_id = current_user.id
    recipe_id = request.form.get('recipe_id')  # get form data

    if not recipe_id:
        return jsonify(message='Missing recipe_id'), 400

    favorite = {
        'user_id': current_user_id,
        'recipe_id': recipe_id
    }
    favourites_collections.insert_one(favorite)
    return jsonify(message='Recipe added to favorites successfully'), 200


@app.route('/favourites')
@login_required
def user_favourites():
    try:
        current_user_id = current_user.id
        user_favorites = favourites_collections.find({'user_id': current_user_id})
        
        favourite_recipe_ids = [favourite['recipe_id'] for favourite in user_favorites]
        print(f"Fetched favorite recipe IDs: {favourite_recipe_ids}")  # Add this line for logging
        
        if not favourite_recipe_ids:
            return render_template('favourites.html', favourites=[])
        
        favourites = recipes_collections.find({'_id': {'$in': favourite_recipe_ids}})
        
        # Convert favorites cursor to list for easier JSON serialization
        favourite_recipes = list(favourites)
        print(f"Fetched favorite recipes: {favourite_recipes}")  # Add this line for logging
        
        return render_template('favourites.html', favourites=favourite_recipes)
    
    except Exception as e:
        print(f"Error fetching favorites: {e}")
        return jsonify(message='Error fetching favorites'), 500



if __name__ == '__main__':
    app.run(debug=True)
