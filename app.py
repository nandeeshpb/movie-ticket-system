"""
Movie Ticket Booking System - Professional Edition
Flask backend with MongoDB database integration
Enhanced with Theaters, Real-time Seat Booking, and Advanced Features
"""

import os
import uuid
import re
import bcrypt
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, redirect, url_for, request, flash, session, jsonify, send_file
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from bson import ObjectId
from pymongo import MongoClient
from config import MONGO_URI, DB_NAME, UPLOAD_FOLDER, ALLOWED_EXTENSIONS, SECRET_KEY
from werkzeug.utils import secure_filename
import qrcode
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# Initialize Flask app
app = Flask(__name__)

# ==================== CUSTOM JINJA2 FILTERS ====================

@app.template_filter('format_date')
def format_date(value):
    """Format dates to '27 Feb 2026' format - handles both datetime objects and strings"""
    if value is None:
        return ''
    if value == '':
        return ''
    try:
        if isinstance(value, datetime):
            return value.strftime('%d %b %Y')
        if isinstance(value, str):
            date_formats = ['%Y-%m-%d', '%Y/%m/%d', '%d-%m-%Y', '%d/%m/%Y', '%B %d, %Y', '%b %d, %Y']
            for fmt in date_formats:
                try:
                    return datetime.strptime(value, fmt).strftime('%d %b %Y')
                except ValueError:
                    continue
            return value
        return str(value)
    except Exception:
        return value if value else ''


@app.template_filter('format_time')
def format_time(value):
    """Format time from 24-hour to 12-hour format (9:30 AM) - handles strings safely"""
    if value is None:
        return ''
    if value == '':
        return ''
    try:
        if isinstance(value, str):
            time_formats = ['%H:%M', '%H:%M:%S', '%I:%M %p', '%I:%M:%S %p']
            for fmt in time_formats:
                try:
                    parsed = datetime.strptime(value, fmt)
                    result = parsed.strftime('%I:%M %p')
                    if result.startswith('0'):
                        result = result[1:]
                    return result
                except ValueError:
                    continue
            if 'AM' in value.upper() or 'PM' in value.upper():
                return value
            try:
                parts = value.split(':')
                if len(parts) >= 2:
                    hour = int(parts[0])
                    minute = parts[1][:2]
                    if hour == 0:
                        return f'12:{minute} AM'
                    elif hour < 12:
                        return f'{hour}:{minute} AM'
                    elif hour == 12:
                        return f'12:{minute} PM'
                    else:
                        return f'{hour-12}:{minute} PM'
            except:
                pass
            return value
        if isinstance(value, datetime):
            result = value.strftime('%I:%M %p')
            if result.startswith('0'):
                result = result[1:]
            return result
        return str(value)
    except Exception:
        return value if value else ''


@app.template_filter('safe_strftime')
def safe_strftime(value, format_str='%d %b %Y'):
    """Safe strftime that handles both datetime objects and strings"""
    if value is None:
        return ''
    if value == '':
        return ''
    try:
        if isinstance(value, datetime):
            return value.strftime(format_str)
        if isinstance(value, str):
            for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%d-%m-%Y', '%d/%m/%Y']:
                try:
                    return datetime.strptime(value, fmt).strftime(format_str)
                except ValueError:
                    continue
            return value
        return str(value)
    except Exception:
        return value if value else ''


@app.template_filter('to_string')
def to_string(value):
    """Convert ObjectId to string for safe display"""
    if isinstance(value, ObjectId):
        return str(value)
    return value if value else ''


# ==================== APP CONFIGURATION ====================

app.secret_key = SECRET_KEY
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize MongoDB
client = MongoClient(MONGO_URI)
db = client[DB_NAME]

# ==================== DATABASE COLLECTIONS ====================
users_collection = db['users']
movies_collection = db['movies']
theaters_collection = db['theaters']
shows_collection = db['shows']
bookings_collection = db['bookings']

# Create indexes
users_collection.create_index('email', unique=True)
movies_collection.create_index('title')
theaters_collection.create_index('name')
shows_collection.create_index([('movie_id', 1), ('theater_id', 1), ('show_date', 1)])
bookings_collection.create_index('booking_id')
bookings_collection.create_index('user_id')
bookings_collection.create_index([('movie_id', 1), ('show_date', 1), ('show_time', 1)])

# ==================== FIXED SHOW TIMES ====================
FIXED_SHOW_TIMES = [
    '09:30',
    '12:30',
    '16:30',
    '21:30'
]

# ==================== SEAT PRICING CATEGORIES ====================
SEAT_CATEGORIES = {
    'silver': {'name': 'Silver', 'price': 200, 'color': '#C0C0C0'},
    'gold': {'name': 'Gold', 'price': 350, 'color': '#FFD700'},
    'platinum': {'name': 'Platinum', 'price': 500, 'color': '#E5E4E2'}
}

# ==================== DEFAULT THEATER SEAT CONFIG ====================
DEFAULT_THEATER_CONFIG = {
    'total_rows': 8,
    'seats_per_row': 12,
    'seat_pricing': {'silver': 200, 'gold': 350, 'platinum': 500}
}

# ==================== ADMIN DECORATOR ====================
def admin_required(f):
    """Decorator to ensure user is admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please login to access this page', 'error')
            return redirect(url_for('login', next=request.url))
        if not current_user.is_admin:
            flash('Access denied. Admin privileges required.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


# ==================== HELPER FUNCTIONS ====================
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_booking_id():
    return 'MB' + str(uuid.uuid4().hex[:10]).upper()

def validate_object_id(id_string):
    """Safely validate ObjectId"""
    if not id_string:
        return None
    try:
        if ObjectId.is_valid(id_string):
            return ObjectId(id_string)
    except:
        pass
    return None

def convert_trailer_url(url):
    """Convert YouTube watch URL to embed URL for better embedding"""
    if not url:
        return ''
    
    url = url.strip()
    
    # Already in embed format
    if 'youtube.com/embed/' in url:
        return url
    
    # Try different YouTube URL patterns
    # Pattern 1: youtube.com/watch?v=VIDEO_ID
    match = re.search(r'[?&]v=([a-zA-Z0-9_-]+)', url)
    if match:
        video_id = match.group(1)
        # Make sure it's 11 characters (YouTube video ID length)
        if len(video_id) >= 11:
            video_id = video_id[:11]
            return f'https://www.youtube.com/embed/{video_id}'
    
    # Pattern 2: youtu.be/VIDEO_ID
    match = re.search(r'youtu\.be/([a-zA-Z0-9_-]+)', url)
    if match:
        video_id = match.group(1)
        if len(video_id) >= 11:
            video_id = video_id[:11]
            return f'https://www.youtube.com/embed/{video_id}'
    
    # Pattern 3: youtube.com/shorts/VIDEO_ID
    match = re.search(r'youtube\.com/shorts/([a-zA-Z0-9_-]+)', url)
    if match:
        video_id = match.group(1)
        if len(video_id) >= 11:
            video_id = video_id[:11]
            return f'https://www.youtube.com/embed/{video_id}'
    
    # Return original URL if not a YouTube link
    return url

def serialize_mongo_doc(doc):
    """Convert MongoDB document to JSON-serializable format"""
    if doc is None:
        return None
    
    if isinstance(doc, list):
        return [serialize_mongo_doc(d) for d in doc]
    
    if isinstance(doc, dict):
        result = {}
        for key, value in doc.items():
            if isinstance(value, ObjectId):
                result[key] = str(value)
            elif isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, dict):
                result[key] = serialize_mongo_doc(value)
            elif isinstance(value, list):
                result[key] = serialize_mongo_doc(value)
            else:
                result[key] = value
        
        # Ensure backward compatibility for theaters without seat_pricing
        if 'seat_pricing' not in result and 'name' in result:
            result['seat_pricing'] = {'silver': 200, 'gold': 350, 'platinum': 500}
        if 'total_rows' not in result and 'name' in result:
            result['total_rows'] = 8
        if 'seats_per_row' not in result and 'name' in result:
            result['seats_per_row'] = 12
        if 'total_seats' not in result and 'name' in result:
            result['total_seats'] = result.get('total_rows', 8) * result.get('seats_per_row', 12)
        if 'seat_categories' not in result and 'name' in result:
            result['seat_categories'] = {}
            
        return result
    
    if isinstance(doc, ObjectId):
        return str(doc)
    
    if isinstance(doc, datetime):
        return doc.isoformat()
    
    return doc

def get_theater_seat_config(theater):
    """Get seat configuration for a theater, with defaults"""
    if not theater:
        return DEFAULT_THEATER_CONFIG.copy()
    
    return {
        'total_rows': theater.get('total_rows', DEFAULT_THEATER_CONFIG['total_rows']),
        'seats_per_row': theater.get('seats_per_row', DEFAULT_THEATER_CONFIG['seats_per_row']),
        'seat_pricing': theater.get('seat_pricing', DEFAULT_THEATER_CONFIG['seat_pricing'])
    }

def generate_seat_categories(total_rows, seats_per_row):
    """Generate seat categories based on row configuration"""
    seat_categories = {}
    for row in range(total_rows):
        row_letter = chr(65 + row)  # A, B, C, etc.
        if row < 2:
            category = 'silver'
        elif row < 5:
            category = 'gold'
        else:
            category = 'platinum'
        
        for seat_num in range(1, seats_per_row + 1):
            seat_id = f"{row_letter}{seat_num}"
            seat_categories[seat_id] = category
    return seat_categories


# ==================== Initialize Flask-Login ====================
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, user_id, name, email, phone, is_admin=False):
        self.id = str(user_id)
        self.name = name
        self.email = email
        self.phone = phone
        self.is_admin = is_admin

@login_manager.user_loader
def load_user(user_id):
    try:
        user = users_collection.find_one({'_id': ObjectId(user_id)})
        if user:
            return User(str(user['_id']), user['name'], user['email'], user.get('phone', ''), user.get('is_admin', False))
    except:
        pass
    return None


# ==================== HOME ROUTE ====================
@app.route('/')
def index():
    movies = serialize_mongo_doc(list(movies_collection.find({'is_active': True})))
    featured_movies = serialize_mongo_doc(list(movies_collection.find({'is_active': True}).sort('created_at', -1).limit(6)))
    upcoming_movies = serialize_mongo_doc(list(movies_collection.find({'is_active': True, 'release_date': {'$gte': datetime.now().strftime('%Y-%m-%d')}}).sort('release_date', 1).limit(4)))
    theaters = serialize_mongo_doc(list(theaters_collection.find({'is_active': True})))
    return render_template('index.html', movies=movies, featured_movies=featured_movies, upcoming_movies=upcoming_movies, theaters=theaters)


# ==================== AUTHENTICATION ROUTES ====================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        errors = []
        if not name or len(name) < 2:
            errors.append('Name must be at least 2 characters')
        if not email or '@' not in email:
            errors.append('Please enter a valid email')
        if not phone or len(phone) < 10:
            errors.append('Please enter a valid phone number')
        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters')
        if password != confirm_password:
            errors.append('Passwords do not match')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return redirect(url_for('register'))
        
        if users_collection.find_one({'email': email}):
            flash('Email already registered', 'error')
            return redirect(url_for('register'))
        
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        user_data = {
            'name': name,
            'email': email,
            'phone': phone,
            'password': hashed_password,
            'is_admin': False,
            'is_active': True,
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        }
        
        users_collection.insert_one(user_data)
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        
        if not email or not password:
            flash('Please enter email and password', 'error')
            return redirect(url_for('login'))
        
        user = users_collection.find_one({'email': email})
        
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password']):
            if not user.get('is_active', True):
                flash('Account is deactivated', 'error')
                return redirect(url_for('login'))
            
            user_obj = User(str(user['_id']), user['name'], user['email'], user.get('phone', ''), user.get('is_admin', False))
            login_user(user_obj)
            flash('Login successful!', 'success')
            
            if user.get('is_admin', False):
                return redirect(url_for('admin_dashboard'))
            
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Invalid email or password', 'error')
            return redirect(url_for('login'))
    
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))


# ==================== MOVIES ROUTES ====================
@app.route('/movies')
def movies_list():
    genre = request.args.get('genre')
    search = request.args.get('search', '').strip()
    
    query = {'is_active': True}
    if genre:
        query['genre'] = genre
    if search:
        query['$or'] = [
            {'title': {'$regex': search, '$options': 'i'}},
            {'description': {'$regex': search, '$options': 'i'}}
        ]
    
    movies = serialize_mongo_doc(list(movies_collection.find(query).sort('created_at', -1)))
    all_movies = serialize_mongo_doc(list(movies_collection.find({'is_active': True})))
    genres = list(set([m.get('genre', 'Other') for m in all_movies]))
    
    return render_template('movies.html', movies=movies, genres=genres, selected_genre=genre, search=search)


@app.route('/movie/<movie_id>')
def movie_details(movie_id):
    oid = validate_object_id(movie_id)
    if not oid:
        flash('Invalid movie ID', 'error')
        return redirect(url_for('movies_list'))
    
    movie = movies_collection.find_one({'_id': oid, 'is_active': True})
    if not movie:
        flash('Movie not found', 'error')
        return redirect(url_for('movies_list'))
    
    theaters = serialize_mongo_doc(list(theaters_collection.find({'is_active': True})))
    showtimes = movie.get('showtimes', [])
    
    return render_template('movie_details.html', movie=movie, showtimes=showtimes, theaters=theaters)


# ==================== THEATERS MANAGEMENT (ADMIN) ====================
@app.route('/admin/theaters')
@admin_required
def manage_theaters():
    theaters = serialize_mongo_doc(list(theaters_collection.find().sort('created_at', -1)))
    return render_template('manage_theaters.html', theaters=theaters)


@app.route('/admin/add_theater', methods=['GET', 'POST'])
@admin_required
def add_theater():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        location = request.form.get('location', '').strip()
        total_seats = int(request.form.get('total_seats', 96))
        total_rows = int(request.form.get('total_rows', 8))
        seats_per_row = int(request.form.get('seats_per_row', 12))
        
        if not name or not location:
            flash('Please fill in all required fields', 'error')
            return redirect(url_for('add_theater'))
        
        # Get seat pricing from form
        silver_price = int(request.form.get('silver_price', 200))
        gold_price = int(request.form.get('gold_price', 350))
        platinum_price = int(request.form.get('platinum_price', 500))
        
        seat_pricing = {
            'silver': silver_price,
            'gold': gold_price,
            'platinum': platinum_price
        }
        
        # Generate seat categories
        seat_categories = generate_seat_categories(total_rows, seats_per_row)
        
        theater_data = {
            'name': name,
            'location': location,
            'total_seats': total_seats,
            'total_rows': total_rows,
            'seats_per_row': seats_per_row,
            'seat_pricing': seat_pricing,
            'seat_categories': seat_categories,
            'is_active': True,
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        }
        
        theaters_collection.insert_one(theater_data)
        flash('Theater added successfully!', 'success')
        return redirect(url_for('manage_theaters'))
    
    return render_template('add_theater.html', seat_categories=SEAT_CATEGORIES)


@app.route('/admin/edit_theater/<theater_id>', methods=['GET', 'POST'])
@admin_required
def edit_theater(theater_id):
    oid = validate_object_id(theater_id)
    if not oid:
        flash('Invalid theater ID', 'error')
        return redirect(url_for('manage_theaters'))
    
    theater = theaters_collection.find_one({'_id': oid})
    if not theater:
        flash('Theater not found', 'error')
        return redirect(url_for('manage_theaters'))
    
    # Inject default seat_pricing if not present (for backward compatibility with old theaters)
    if 'seat_pricing' not in theater:
        theater['seat_pricing'] = {
            'silver': 200,
            'gold': 350,
            'platinum': 500
        }
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        location = request.form.get('location', '').strip()
        total_seats = int(request.form.get('total_seats', 96))
        total_rows = int(request.form.get('total_rows', 8))
        seats_per_row = int(request.form.get('seats_per_row', 12))
        
        if not name or not location:
            flash('Please fill in all required fields', 'error')
            return redirect(url_for('edit_theater', theater_id=theater_id))
        
        # Get seat pricing from form
        silver_price = int(request.form.get('silver_price', 200))
        gold_price = int(request.form.get('gold_price', 350))
        platinum_price = int(request.form.get('platinum_price', 500))
        
        seat_pricing = {
            'silver': silver_price,
            'gold': gold_price,
            'platinum': platinum_price
        }
        
        # Regenerate seat categories
        seat_categories = generate_seat_categories(total_rows, seats_per_row)
        
        theaters_collection.update_one(
            {'_id': oid},
            {'$set': {
                'name': name,
                'location': location,
                'total_seats': total_seats,
                'total_rows': total_rows,
                'seats_per_row': seats_per_row,
                'seat_pricing': seat_pricing,
                'seat_categories': seat_categories,
                'updated_at': datetime.now()
            }}
        )
        flash('Theater updated successfully!', 'success')
        return redirect(url_for('manage_theaters'))
    
    return render_template('edit_theater.html', theater=theater, seat_categories=SEAT_CATEGORIES)


@app.route('/admin/delete_theater/<theater_id>')
@admin_required
def delete_theater(theater_id):
    oid = validate_object_id(theater_id)
    if not oid:
        flash('Invalid theater ID', 'error')
        return redirect(url_for('manage_theaters'))
    
    theaters_collection.update_one({'_id': oid}, {'$set': {'is_active': False}})
    flash('Theater deleted successfully!', 'success')
    return redirect(url_for('manage_theaters'))


# ==================== ADMIN DASHBOARD ====================
@app.route('/admin')
@admin_required
def admin_dashboard():
    total_users = users_collection.count_documents({'is_admin': False})
    total_bookings = bookings_collection.count_documents({})
    total_movies = movies_collection.count_documents({'is_active': True})
    total_theaters = theaters_collection.count_documents({'is_active': True})
    
    pipeline = [{'$group': {'_id': None, 'total': {'$sum': '$total_amount'}}}]
    revenue_result = list(bookings_collection.aggregate(pipeline))
    total_revenue = revenue_result[0]['total'] if revenue_result else 0
    
    recent_bookings = list(bookings_collection.find().sort('created_at', -1).limit(10))
    users = list(users_collection.find({'is_admin': False}))
    
    return render_template('admin_dashboard.html', 
                           total_users=total_users,
                           total_bookings=total_bookings,
                           total_movies=total_movies,
                           total_theaters=total_theaters,
                           total_revenue=total_revenue,
                           recent_bookings=recent_bookings,
                           users=users)


# ==================== MOVIE MANAGEMENT (ADMIN) ====================

@app.route('/admin/movies')
@admin_required
def admin_movies():
    """Admin page to list all movies with edit options"""
    movies = list(movies_collection.find().sort('created_at', -1))
    # Convert ObjectId to string for Jinja template compatibility
    for movie in movies:
        movie['_id'] = str(movie['_id'])
    movies = serialize_mongo_doc(movies)
    return render_template('admin_movies.html', movies=movies)


@app.route('/admin/add_movie', methods=['GET', 'POST'])
@admin_required
def add_movie():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        genre = request.form.get('genre', '').strip()
        duration = request.form.get('duration', '').strip()
        release_date = request.form.get('release_date', '').strip()
        ticket_price = float(request.form.get('ticket_price', 0))
        trailer_link = request.form.get('trailer_link', '').strip()
        showtimes = request.form.getlist('showtimes')
        
        poster_filename = 'default_movie.jpg'
        if 'poster' in request.files:
            file = request.files['poster']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                poster_filename = str(uuid.uuid4()) + '_' + filename
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], poster_filename))
        
        if not title or not genre or not duration:
            flash('Please fill in all required fields', 'error')
            return redirect(url_for('add_movie'))
        
        movie_data = {
            'title': title,
            'description': description,
            'genre': genre,
            'duration': duration,
            'release_date': release_date,
            'ticket_price': ticket_price,
            'trailer_link': trailer_link,
            'showtimes': showtimes,
            'poster': poster_filename,
            'is_active': True,
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
            'booked_seats': {}
        }
        
        movies_collection.insert_one(movie_data)
        flash('Movie added successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('add_movie.html', fixed_show_times=FIXED_SHOW_TIMES)


@app.route('/admin/edit_movie/<movie_id>', methods=['GET', 'POST'])
@admin_required
def edit_movie(movie_id):
    """Edit movie - GET shows form, POST handles update"""
    oid = validate_object_id(movie_id)
    if not oid:
        flash('Invalid movie ID', 'error')
        return redirect(url_for('admin_movies'))
    
    movie = movies_collection.find_one({'_id': oid})
    if not movie:
        flash('Movie not found', 'error')
        return redirect(url_for('admin_movies'))
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        genre = request.form.get('genre', '').strip()
        duration = request.form.get('duration', '').strip()
        release_date = request.form.get('release_date', '').strip()
        ticket_price = float(request.form.get('ticket_price', 0))
        trailer_link = request.form.get('trailer_link', '').strip()
        showtimes = request.form.getlist('showtimes')
        language = request.form.get('language', '').strip()
        status = request.form.get('status', 'Now Showing')
        
        # Convert trailer URL to embed format
        trailer_url = convert_trailer_url(trailer_link)
        
        poster_filename = movie.get('poster', 'default_movie.jpg')
        if 'poster' in request.files:
            file = request.files['poster']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                poster_filename = str(uuid.uuid4()) + '_' + filename
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], poster_filename))
        
        movies_collection.update_one(
            {'_id': oid},
            {'$set': {
                'title': title,
                'description': description,
                'genre': genre,
                'duration': duration,
                'release_date': release_date,
                'ticket_price': ticket_price,
                'trailer_link': trailer_link,
                'trailer_url': trailer_url,
                'showtimes': showtimes,
                'poster': poster_filename,
                'language': language,
                'status': status,
                'updated_at': datetime.now()
            }}
        )
        flash('Movie updated successfully!', 'success')
        return redirect(url_for('admin_movies'))
    
    return render_template('edit_movie.html', movie=movie, fixed_show_times=FIXED_SHOW_TIMES)


@app.route('/admin/update_movie/<movie_id>', methods=['POST'])
@admin_required
def update_movie(movie_id):
    """Separate route for updating movie details - handles form submission"""
    oid = validate_object_id(movie_id)
    if not oid:
        flash('Invalid movie ID', 'error')
        return redirect(url_for('admin_movies'))
    
    movie = movies_collection.find_one({'_id': oid})
    if not movie:
        flash('Movie not found', 'error')
        return redirect(url_for('admin_movies'))
    
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    genre = request.form.get('genre', '').strip()
    duration = request.form.get('duration', '').strip()
    release_date = request.form.get('release_date', '').strip()
    ticket_price = float(request.form.get('ticket_price', 0))
    trailer_link = request.form.get('trailer_link', '').strip()
    showtimes = request.form.getlist('showtimes')
    language = request.form.get('language', '').strip()
    status = request.form.get('status', 'Now Showing')
    
    # Convert trailer URL to embed format
    trailer_url = convert_trailer_url(trailer_link)
    
    poster_filename = movie.get('poster', 'default_movie.jpg')
    if 'poster' in request.files:
        file = request.files['poster']
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            poster_filename = str(uuid.uuid4()) + '_' + filename
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], poster_filename))
    
    movies_collection.update_one(
        {'_id': oid},
        {'$set': {
            'title': title,
            'description': description,
            'genre': genre,
            'duration': duration,
            'release_date': release_date,
            'ticket_price': ticket_price,
            'trailer_link': trailer_link,
            'trailer_url': trailer_url,
            'showtimes': showtimes,
            'poster': poster_filename,
            'language': language,
            'status': status,
            'updated_at': datetime.now()
        }}
    )
    flash('Movie updated successfully!', 'success')
    return redirect(url_for('admin_movies'))


@app.route('/admin/delete_movie/<movie_id>')
@admin_required
def delete_movie(movie_id):
    oid = validate_object_id(movie_id)
    if not oid:
        flash('Invalid movie ID', 'error')
        return redirect(url_for('admin_movies'))
    
    movies_collection.update_one({'_id': oid}, {'$set': {'is_active': False}})
    flash('Movie deleted successfully!', 'success')
    return redirect(url_for('admin_movies'))


@app.route('/admin/reactivate_movie/<movie_id>')
@admin_required
def reactivate_movie(movie_id):
    """Reactivate a previously deleted movie"""
    oid = validate_object_id(movie_id)
    if not oid:
        flash('Invalid movie ID', 'error')
        return redirect(url_for('admin_movies'))
    
    movies_collection.update_one({'_id': oid}, {'$set': {'is_active': True}})
    flash('Movie reactivated successfully!', 'success')
    return redirect(url_for('admin_movies'))


@app.route('/admin/manage_users')
@admin_required
def manage_users():
    users = list(users_collection.find({'is_admin': False}))
    return render_template('manage_users.html', users=users)


@app.route('/admin/toggle_user_status/<user_id>')
@admin_required
def toggle_user_status(user_id):
    oid = validate_object_id(user_id)
    if not oid:
        flash('Invalid user ID', 'error')
        return redirect(url_for('manage_users'))
    
    user = users_collection.find_one({'_id': oid})
    if user:
        new_status = not user.get('is_active', True)
        users_collection.update_one({'_id': oid}, {'$set': {'is_active': new_status}})
        flash(f'User status updated to {"active" if new_status else "inactive"}', 'success')
    else:
        flash('User not found', 'error')
    
    return redirect(url_for('manage_users'))


@app.route('/admin/all_bookings')
@admin_required
def all_bookings():
    bookings = list(bookings_collection.find().sort('created_at', -1))
    return render_template('all_bookings.html', bookings=bookings)


# ==================== BOOKING ROUTES ====================
@app.route('/booking/<movie_id>', methods=['GET', 'POST'])
def booking(movie_id):
    oid = validate_object_id(movie_id)
    if not oid:
        flash('Invalid movie ID', 'error')
        return redirect(url_for('movies_list'))
    
    movie = movies_collection.find_one({'_id': oid, 'is_active': True})
    if not movie:
        flash('Movie not found', 'error')
        return redirect(url_for('movies_list'))
    
    if request.method == 'POST':
        if not current_user.is_authenticated:
            return jsonify({'success': False, 'message': 'Please login to book tickets'}), 401
        
        show_date = request.form.get('show_date', '').strip()
        show_time = request.form.get('show_time', '').strip()
        theater_id = request.form.get('theater_id', '').strip()
        selected_seats = request.form.getlist('seats')
        
        if selected_seats and isinstance(selected_seats[0], str) and ',' in selected_seats[0]:
            selected_seats = selected_seats[0].split(',')
        
        try:
            frontend_seat_count = int(request.form.get('seat_count', 0))
            frontend_total = float(request.form.get('total_amount', 0))
        except:
            frontend_seat_count = 0
            frontend_total = 0
        
        # Validation
        if not show_date:
            return jsonify({'success': False, 'message': 'Please select a show date'})
        if not show_time:
            return jsonify({'success': False, 'message': 'Please select a show time'})
        if not theater_id:
            return jsonify({'success': False, 'message': 'Please select a theater'})
        if not selected_seats or len(selected_seats) == 0:
            return jsonify({'success': False, 'message': 'Please select at least one seat'})
        
        # Validate seat format
        seat_pattern = r'^[A-Z][1-9]\d?$'
        for seat in selected_seats:
            if not re.match(seat_pattern, seat.strip().upper()):
                return jsonify({'success': False, 'message': 'Invalid seat format: ' + seat})
        selected_seats = [s.strip().upper() for s in selected_seats]
        
        # Validate date format
        try:
            datetime.strptime(show_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid date format'})
        
        # Validate showtime format (must be from fixed times)
        if show_time not in FIXED_SHOW_TIMES:
            return jsonify({'success': False, 'message': 'Invalid showtime selected'})
        
        # Get theater info
        theater_oid = validate_object_id(theater_id)
        
        if not theater_oid:
            return jsonify({'success': False, 'message': 'Invalid theater'})
        
        theater = theaters_collection.find_one({'_id': theater_oid, 'is_active': True})
        
        if not theater:
            return jsonify({'success': False, 'message': 'Theater not found'})
        
        # Get theater seat configuration
        seat_config = get_theater_seat_config(theater)
        seat_categories = theater.get('seat_categories', seat_config.get('seat_categories', {}))
        seat_pricing = theater.get('seat_pricing', seat_config.get('seat_pricing', {'silver': 200, 'gold': 350, 'platinum': 500}))
        
        # Check for double booking
        existing_booking = bookings_collection.find_one({
            'movie_id': str(movie['_id']),
            'theater_id': theater_id,
            'show_date': show_date,
            'show_time': show_time,
            'seats': {'$in': selected_seats},
            'status': {'$ne': 'cancelled'}
        })
        
        if existing_booking:
            booked = ', '.join(selected_seats)
            return jsonify({'success': False, 'message': f'Seat(s) {booked} already booked. Please select different seats.'})
        
        # Calculate total price based on seat categories
        backend_total = 0
        for seat in selected_seats:
            category = seat_categories.get(seat, 'silver')
            backend_total += seat_pricing.get(category, 200)
        
        # Validate seat count
        backend_seat_count = len(selected_seats)
        if backend_seat_count != frontend_seat_count:
            return jsonify({'success': False, 'message': 'Seat count mismatch. Please refresh and try again.'})
        
        # Validate total amount
        if abs(backend_total - frontend_total) > 1:
            return jsonify({'success': False, 'message': 'Total amount mismatch. Please refresh and try again.'})
        
        # Create booking
        booking_id = generate_booking_id()
        
        # Store seat details with categories
        seat_details = []
        for seat in selected_seats:
            category = seat_categories.get(seat, 'silver')
            price = seat_pricing.get(category, 200)
            seat_details.append({
                'seat': seat,
                'category': category,
                'price': price
            })
        
        booking_data = {
            'booking_id': booking_id,
            'user_id': str(current_user.id),
            'user_name': current_user.name,
            'user_email': current_user.email,
            'movie_id': str(movie['_id']),
            'movie_title': movie['title'],
            'theater_id': theater_id,
            'theater_name': theater['name'],
            'show_date': show_date,
            'show_time': show_time,
            'seats': selected_seats,
            'seat_details': seat_details,
            'seat_count': backend_seat_count,
            'price_per_seat': seat_pricing,
            'total_amount': backend_total,
            'status': 'pending',
            'created_at': datetime.now()
        }
        
        # Store booking temporarily in session for payment
        session['pending_booking'] = booking_data
        
        return jsonify({
            'success': True, 
            'message': 'Redirecting to payment...', 
            'redirect': url_for('payment_page')
        })
    
    # Get available dates
    today = datetime.now()
    available_dates = [today + timedelta(days=i) for i in range(7)]
    showtimes = movie.get('showtimes', FIXED_SHOW_TIMES)
    theaters = serialize_mongo_doc(list(theaters_collection.find({'is_active': True})))
    
    return render_template('booking.html', 
                          movie=movie, 
                          available_dates=available_dates, 
                          showtimes=showtimes,
                          theaters=theaters,
                          fixed_show_times=FIXED_SHOW_TIMES,
                          seat_categories=SEAT_CATEGORIES)


# ==================== REAL-TIME SEAT BOOKING API ====================
@app.route('/get_booked_seats/<movie_id>/<theater_id>/<show_date>/<show_time>')
def get_booked_seats(movie_id, theater_id, show_date, show_time):
    """API endpoint to get real-time booked seats"""
    try:
        # Validate all IDs
        movie_oid = validate_object_id(movie_id)
        theater_oid = validate_object_id(theater_id)
        
        if not movie_oid or not theater_oid:
            return jsonify({'success': False, 'booked_seats': []})
        
        movie = movies_collection.find_one({'_id': movie_oid})
        if not movie:
            return jsonify({'success': False, 'booked_seats': []})
        
        all_booked = []
        
        # Get from movies collection
        key = f"{show_date}_{theater_id}_{show_time}"
        movie_seats = movie.get('booked_seats', {}).get(key, [])
        all_booked.extend(movie_seats)
        
        # Get from bookings collection
        bookings = bookings_collection.find({
            'movie_id': movie_id,
            'theater_id': theater_id,
            'show_date': show_date,
            'show_time': show_time,
            'status': {'$ne': 'cancelled'}
        })
        for b in bookings:
            if 'seats' in b and isinstance(b['seats'], list):
                for s in b['seats']:
                    if s not in all_booked:
                        all_booked.append(s)
        
        return jsonify({'success': True, 'booked_seats': all_booked})
    except Exception as e:
        return jsonify({'success': False, 'booked_seats': [], 'error': str(e)})


@app.route('/get_theater_info/<theater_id>')
def get_theater_info(theater_id):
    """Get theater information including seat layout and pricing"""
    try:
        theater_oid = validate_object_id(theater_id)
        if not theater_oid:
            return jsonify({'success': False})
        
        theater = theaters_collection.find_one({'_id': theater_oid, 'is_active': True})
        if not theater:
            return jsonify({'success': False})
        
        seat_config = get_theater_seat_config(theater)
        
        return jsonify({
            'success': True,
            'theater': {
                'total_rows': seat_config['total_rows'],
                'seats_per_row': seat_config['seats_per_row'],
                'seat_pricing': seat_config['seat_pricing'],
                'seat_categories': theater.get('seat_categories', {}),
                'total_seats': theater.get('total_seats', seat_config['total_rows'] * seat_config['seats_per_row'])
            },
            'theater_name': theater['name']
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ==================== PAYMENT PAGE ====================
@app.route('/payment')
@login_required
def payment_page():
    """Display payment page with booking details"""
    pending_booking = session.get('pending_booking')
    
    if not pending_booking:
        flash('No pending booking found', 'error')
        return redirect(url_for('movies_list'))
    
    # Get movie details
    movie = movies_collection.find_one({'_id': ObjectId(pending_booking['movie_id'])})
    if not movie:
        flash('Movie not found', 'error')
        return redirect(url_for('movies_list'))
    
    # Get theater details
    theater = theaters_collection.find_one({'_id': ObjectId(pending_booking['theater_id'])})
    
    return render_template('payment.html', 
                          booking=pending_booking,
                          movie=movie,
                          theater=theater)


@app.route('/process_payment', methods=['POST'])
@login_required
def process_payment():
    """Process payment and confirm booking"""
    pending_booking = session.get('pending_booking')
    
    if not pending_booking:
        flash('No pending booking found', 'error')
        return redirect(url_for('movies_list'))
    
    payment_method = request.form.get('payment_method', '')
    
    if not payment_method:
        flash('Please select a payment method', 'error')
        return redirect(url_for('payment_page'))
    
    try:
        # Check for double booking again before confirming
        existing_booking = bookings_collection.find_one({
            'movie_id': pending_booking['movie_id'],
            'theater_id': pending_booking['theater_id'],
            'show_date': pending_booking['show_date'],
            'show_time': pending_booking['show_time'],
            'seats': {'$in': pending_booking['seats']},
            'status': {'$ne': 'cancelled'}
        })
        
        if existing_booking:
            flash('One or more seats have been booked. Please select different seats.', 'error')
            session.pop('pending_booking', None)
            return redirect(url_for('movies_list'))
        
        # Add payment method to booking
        pending_booking['payment_method'] = payment_method
        pending_booking['status'] = 'confirmed'
        
        # Insert booking into database
        bookings_collection.insert_one(pending_booking)
        
        # Update booked seats in movie
        movies_collection.update_one(
            {'_id': ObjectId(pending_booking['movie_id'])},
            {'$set': {f"booked_seats.{pending_booking['show_date']}_{pending_booking['theater_id']}_{pending_booking['show_time']}": pending_booking['seats']}}
        )
        
        # Clear pending booking from session
        session.pop('pending_booking', None)
        
        flash('Payment successful! Booking confirmed.', 'success')
        return redirect(url_for('booking_confirmation', booking_id=pending_booking['booking_id']))
        
    except Exception as e:
        flash(f'Error processing payment: {str(e)}', 'error')
        return redirect(url_for('payment_page'))


@app.route('/cancel_booking_session')
@login_required
def cancel_booking_session():
    """Cancel pending booking session"""
    session.pop('pending_booking', None)
    flash('Booking cancelled', 'info')
    return redirect(url_for('movies_list'))


# ==================== BOOKING CONFIRMATION ====================
@app.route('/booking_confirmation/<booking_id>')
def booking_confirmation(booking_id):
    try:
        booking = bookings_collection.find_one({'booking_id': booking_id})
        if not booking:
            flash('Booking not found', 'error')
            return redirect(url_for('index'))
        
        if current_user.is_authenticated:
            if not current_user.is_admin and booking.get('user_id') != str(current_user.id):
                flash('Access denied', 'error')
                return redirect(url_for('index'))
        else:
            flash('Please login to view booking', 'error')
            return redirect(url_for('login'))
        
        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr_data = f"Booking ID: {booking_id}\nMovie: {booking['movie_title']}\nTheater: {booking.get('theater_name', 'N/A')}\nDate: {booking['show_date']}\nTime: {booking['show_time']}\nSeats: {', '.join(booking['seats'])}"
        qr.add_data(qr_data)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        # Save QR code to file
        qr_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'qr_codes')
        os.makedirs(qr_folder, exist_ok=True)
        qr_filename = f"booking_{booking_id}.png"
        qr_path = os.path.join(qr_folder, qr_filename)
        qr_img.save(qr_path)
        
        qr_base64 = None
        with open(qr_path, 'rb') as f:
            import base64
            qr_base64 = base64.b64encode(f.read()).decode('utf-8')
        
        return render_template('booking_confirmation.html', booking=booking, qr_code=qr_base64)
    except Exception as e:
        flash('Error: ' + str(e), 'error')
        return redirect(url_for('index'))


@app.route('/download_ticket/<booking_id>')
def download_ticket(booking_id):
    try:
        booking = bookings_collection.find_one({'booking_id': booking_id})
        if not booking:
            flash('Booking not found', 'error')
            return redirect(url_for('index'))
        
        if current_user.is_authenticated:
            if not current_user.is_admin and booking.get('user_id') != str(current_user.id):
                flash('Access denied', 'error')
                return redirect(url_for('index'))
        
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        
        p.setFont("Helvetica-Bold", 24)
        p.drawString(100, 700, "MOVIE TICKET")
        
        p.setFont("Helvetica", 12)
        p.drawString(100, 660, "Booking ID: " + booking['booking_id'])
        p.drawString(100, 640, "Movie: " + booking['movie_title'])
        p.drawString(100, 620, "Theater: " + booking.get('theater_name', 'N/A'))
        p.drawString(100, 600, "Date: " + booking['show_date'])
        p.drawString(100, 580, "Time: " + booking['show_time'])
        p.drawString(100, 560, "Seats: " + ', '.join(booking['seats']))
        p.drawString(100, 540, "Tickets: " + str(booking['seat_count']))
        p.drawString(100, 520, "Total Amount: Rs. " + str(booking['total_amount']))
        p.drawString(100, 500, "Status: " + booking['status'].upper())
        
        p.showPage()
        p.save()
        
        buffer.seek(0)
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name='ticket_' + booking_id + '.pdf',
            mimetype='application/pdf'
        )
    except Exception as e:
        flash('Error generating ticket: ' + str(e), 'error')
        return redirect(url_for('index'))


# ==================== USER DASHBOARD ====================
@app.route('/dashboard')
@login_required
def user_dashboard():
    user_bookings = list(bookings_collection.find({'user_id': str(current_user.id)}).sort('created_at', -1))
    total_bookings = len(user_bookings)
    total_spent = sum(b.get('total_amount', 0) for b in user_bookings)
    
    return render_template('user_dashboard.html', 
                           bookings=user_bookings,
                           total_bookings=total_bookings,
                           total_spent=total_spent)


@app.route('/cancel_booking/<booking_id>')
@login_required
def cancel_booking(booking_id):
    try:
        booking = bookings_collection.find_one({'booking_id': booking_id, 'user_id': str(current_user.id)})
        if not booking:
            flash('Booking not found', 'error')
            return redirect(url_for('user_dashboard'))
        
        if booking.get('status') == 'cancelled':
            flash('Booking already cancelled', 'error')
            return redirect(url_for('user_dashboard'))
        
        bookings_collection.update_one(
            {'booking_id': booking_id},
            {'$set': {'status': 'cancelled', 'cancelled_at': datetime.now()}}
        )
        
        # Release seats
        movie_id = booking.get('movie_id')
        theater_id = booking.get('theater_id')
        show_date = booking.get('show_date')
        show_time = booking.get('show_time')
        seats = booking.get('seats', [])
        
        movie = movies_collection.find_one({'_id': ObjectId(movie_id)})
        if movie:
            key = f"{show_date}_{theater_id}_{show_time}"
            booked_seats = movie.get('booked_seats', {}).get(key, [])
            updated_seats = [s for s in booked_seats if s not in seats]
            movies_collection.update_one(
                {'_id': ObjectId(movie_id)},
                {'$set': {key: updated_seats}}
            )
        
        flash('Booking cancelled successfully', 'success')
        return redirect(url_for('user_dashboard'))
    except Exception as e:
        flash('Error: ' + str(e), 'error')
        return redirect(url_for('user_dashboard'))


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        
        if not name or len(name) < 2:
            flash('Name must be at least 2 characters', 'error')
            return redirect(url_for('profile'))
        
        users_collection.update_one(
            {'_id': ObjectId(current_user.id)},
            {'$set': {'name': name, 'phone': phone, 'updated_at': datetime.now()}}
        )
        
        flash('Profile updated successfully', 'success')
        return redirect(url_for('profile'))
    
    user = users_collection.find_one({'_id': ObjectId(current_user.id)})
    return render_template('profile.html', user=user)


# ==================== ERROR HANDLERS ====================
@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500


# ==================== INITIALIZE DEFAULT ADMIN ====================
def init_admin():
    admin = users_collection.find_one({'email': 'admin@movie.com'})
    if not admin:
        hashed_password = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt())
        admin_data = {
            'name': 'Admin',
            'email': 'admin@movie.com',
            'phone': '1234567890',
            'password': hashed_password,
            'is_admin': True,
            'is_active': True,
            'created_at': datetime.now()
        }
        users_collection.insert_one(admin_data)
        print("Admin account created: admin@movie.com / admin123")


if __name__ == '__main__':
    init_admin()
    app.run(debug=True, port=5000)
