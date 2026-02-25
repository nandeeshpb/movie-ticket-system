"""
Movie Ticket Booking System - Main Application
Flask backend with MongoDB database integration
"""

import os
import uuid
import bcrypt
from datetime import datetime, timedelta
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
app.secret_key = SECRET_KEY

# Configure upload folder
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize MongoDB
client = MongoClient(MONGO_URI)
db = client[DB_NAME]

# Collections
users_collection = db['users']
movies_collection = db['movies']
bookings_collection = db['bookings']

# Create indexes
users_collection.create_index('email', unique=True)
movies_collection.create_index('title')
bookings_collection.create_index('booking_id')
bookings_collection.create_index('user_id')

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User class for Flask-Login
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

# Helper function to check allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Helper function to generate unique booking ID
def generate_booking_id():
    return 'MB' + str(uuid.uuid4().hex[:10]).upper()

# ==================== ROUTES ====================

# Home Page
@app.route('/')
def index():
    # Get all movies
    movies = list(movies_collection.find({'is_active': True}))
    
    # Featured movies (latest 6)
    featured_movies = list(movies_collection.find({'is_active': True}).sort('created_at', -1).limit(6))
    
    # Get upcoming movies
    upcoming_movies = list(movies_collection.find({'is_active': True, 'release_date': {'$gte': datetime.now().strftime('%Y-%m-%d')}}).sort('release_date', 1).limit(4))
    
    return render_template('index.html', movies=movies, featured_movies=featured_movies, upcoming_movies=upcoming_movies)

# Authentication Routes
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
        
        # Validation
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
        
        # Check if user exists
        if users_collection.find_one({'email': email}):
            flash('Email already registered', 'error')
            return redirect(url_for('register'))
        
        # Hash password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        # Create user
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
        
        user_id = users_collection.insert_one(user_data).inserted_id
        
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
        
        # Find user
        user = users_collection.find_one({'email': email})
        
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password']):
            if not user.get('is_active', True):
                flash('Account is deactivated', 'error')
                return redirect(url_for('login'))
            
            user_obj = User(str(user['_id']), user['name'], user['email'], user.get('phone', ''), user.get('is_admin', False))
            login_user(user_obj)
            
            flash('Login successful!', 'success')
            
            # Redirect to admin dashboard if admin
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

# Movies Routes
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
    
    movies = list(movies_collection.find(query).sort('created_at', -1))
    
    # Get unique genres
    all_movies = list(movies_collection.find({'is_active': True}))
    genres = list(set([m.get('genre', 'Other') for m in all_movies]))
    
    return render_template('movies.html', movies=movies, genres=genres, selected_genre=genre, search=search)

@app.route('/movie/<movie_id>')
def movie_details(movie_id):
    try:
        movie = movies_collection.find_one({'_id': ObjectId(movie_id), 'is_active': True})
        if not movie:
            flash('Movie not found', 'error')
            return redirect(url_for('movies_list'))
        
        # Get showtimes
        showtimes = movie.get('showtimes', [])
        
        return render_template('movie_details.html', movie=movie, showtimes=showtimes)
    except:
        flash('Invalid movie ID', 'error')
        return redirect(url_for('movies_list'))

# Admin Routes
@app.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    # Get statistics
    total_users = users_collection.count_documents({'is_admin': False})
    total_bookings = bookings_collection.count_documents({})
    total_movies = movies_collection.count_documents({'is_active': True})
    
    # Calculate total revenue
    pipeline = [
        {'$group': {'_id': None, 'total': {'$sum': '$total_amount'}}}
    ]
    revenue_result = list(bookings_collection.aggregate(pipeline))
    total_revenue = revenue_result[0]['total'] if revenue_result else 0
    
    # Recent bookings
    recent_bookings = list(bookings_collection.find().sort('created_at', -1).limit(10))
    
    # Get users for management
    users = list(users_collection.find({'is_admin': False}))
    
    return render_template('admin_dashboard.html', 
                           total_users=total_users,
                           total_bookings=total_bookings,
                           total_movies=total_movies,
                           total_revenue=total_revenue,
                           recent_bookings=recent_bookings,
                           users=users)

@app.route('/admin/add_movie', methods=['GET', 'POST'])
@login_required
def add_movie():
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        genre = request.form.get('genre', '').strip()
        duration = request.form.get('duration', '').strip()
        release_date = request.form.get('release_date', '').strip()
        ticket_price = float(request.form.get('ticket_price', 0))
        trailer_link = request.form.get('trailer_link', '').strip()
        showtimes = request.form.getlist('showtimes')
        
        # Handle poster upload
        poster_filename = 'default_movie.jpg'
        if 'poster' in request.files:
            file = request.files['poster']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # Add unique identifier to filename
                poster_filename = str(uuid.uuid4()) + '_' + filename
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], poster_filename))
        
        # Validation
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
            'booked_seats': {}  # Dictionary to store booked seats per showtime
        }
        
        movies_collection.insert_one(movie_data)
        flash('Movie added successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('add_movie.html')

@app.route('/admin/edit_movie/<movie_id>', methods=['GET', 'POST'])
@login_required
def edit_movie(movie_id):
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    try:
        movie = movies_collection.find_one({'_id': ObjectId(movie_id)})
        if not movie:
            flash('Movie not found', 'error')
            return redirect(url_for('admin_dashboard'))
        
        if request.method == 'POST':
            title = request.form.get('title', '').strip()
            description = request.form.get('description', '').strip()
            genre = request.form.get('genre', '').strip()
            duration = request.form.get('duration', '').strip()
            release_date = request.form.get('release_date', '').strip()
            ticket_price = float(request.form.get('ticket_price', 0))
            trailer_link = request.form.get('trailer_link', '').strip()
            showtimes = request.form.getlist('showtimes')
            
            # Handle poster upload
            poster_filename = movie.get('poster', 'default_movie.jpg')
            if 'poster' in request.files:
                file = request.files['poster']
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    poster_filename = str(uuid.uuid4()) + '_' + filename
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], poster_filename))
            
            update_data = {
                'title': title,
                'description': description,
                'genre': genre,
                'duration': duration,
                'release_date': release_date,
                'ticket_price': ticket_price,
                'trailer_link': trailer_link,
                'showtimes': showtimes,
                'poster': poster_filename,
                'updated_at': datetime.now()
            }
            
            movies_collection.update_one({'_id': ObjectId(movie_id)}, {'$set': update_data})
            flash('Movie updated successfully!', 'success')
            return redirect(url_for('admin_dashboard'))
        
        return render_template('edit_movie.html', movie=movie)
    except:
        flash('Invalid movie ID', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_movie/<movie_id>')
@login_required
def delete_movie(movie_id):
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    try:
        movies_collection.update_one({'_id': ObjectId(movie_id)}, {'$set': {'is_active': False}})
        flash('Movie deleted successfully!', 'success')
    except:
        flash('Invalid movie ID', 'error')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/manage_users')
@login_required
def manage_users():
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    users = list(users_collection.find({'is_admin': False}))
    return render_template('manage_users.html', users=users)

@app.route('/admin/toggle_user_status/<user_id>')
@login_required
def toggle_user_status(user_id):
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    try:
        user = users_collection.find_one({'_id': ObjectId(user_id)})
        if user:
            new_status = not user.get('is_active', True)
            users_collection.update_one({'_id': ObjectId(user_id)}, {'$set': {'is_active': new_status}})
            flash(f'User status updated to {"active" if new_status else "inactive"}', 'success')
    except:
        flash('Invalid user ID', 'error')
    
    return redirect(url_for('manage_users'))

@app.route('/admin/all_bookings')
@login_required
def all_bookings():
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    bookings = list(bookings_collection.find().sort('created_at', -1))
    return render_template('all_bookings.html', bookings=bookings)

# Booking Routes
@app.route('/booking/<movie_id>', methods=['GET', 'POST'])
def booking(movie_id):
    try:
        movie = movies_collection.find_one({'_id': ObjectId(movie_id), 'is_active': True})
        if not movie:
            flash('Movie not found', 'error')
            return redirect(url_for('movies_list'))
        
        if request.method == 'POST':
            if not current_user.is_authenticated:
                flash('Please login to book tickets', 'error')
                return redirect(url_for('login'))
            
            show_date = request.form.get('show_date')
            show_time = request.form.get('show_time')
            selected_seats = request.form.getlist('seats')
            
            if not show_date or not show_time or not selected_seats:
                flash('Please select show date, time and seats', 'error')
                return redirect(url_for('booking', movie_id=movie_id))
            
            # Check if seats are already booked
            booked_seats = movie.get('booked_seats', {}).get(f"{show_date}_{show_time}", [])
            for seat in selected_seats:
                if seat in booked_seats:
                    flash(f'Seat {seat} is already booked', 'error')
                    return redirect(url_for('booking', movie_id=movie_id))
            
            # Calculate total amount
            ticket_price = movie.get('ticket_price', 300)
            total_amount = len(selected_seats) * ticket_price
            
            # Generate booking ID
            booking_id = generate_booking_id()
            
            # Create booking
            booking_data = {
                'booking_id': booking_id,
                'user_id': str(current_user.id),
                'user_name': current_user.name,
                'user_email': current_user.email,
                'movie_id': str(movie['_id']),
                'movie_title': movie['title'],
                'show_date': show_date,
                'show_time': show_time,
                'seats': selected_seats,
                'seat_count': len(selected_seats),
                'ticket_price': ticket_price,
                'total_amount': total_amount,
                'status': 'confirmed',
                'created_at': datetime.now()
            }
            
            bookings_collection.insert_one(booking_data)
            
            # Update booked seats in movie
            movies_collection.update_one(
                {'_id': ObjectId(movie_id)},
                {'$set': {f'booked_seats.{show_date}_{show_time}': booked_seats + selected_seats}}
            )
            
            flash(f'Booking successful! Your booking ID is {booking_id}', 'success')
            return redirect(url_for('booking_confirmation', booking_id=booking_id))
        
        # Get available dates (next 7 days)
        today = datetime.now()
        available_dates = [(today + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]
        
        showtimes = movie.get('showtimes', [])
        
        return render_template('booking.html', movie=movie, available_dates=available_dates, showtimes=showtimes)
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('movies_list'))

@app.route('/booking_confirmation/<booking_id>')
def booking_confirmation(booking_id):
    try:
        booking = bookings_collection.find_one({'booking_id': booking_id})
        if not booking:
            flash('Booking not found', 'error')
            return redirect(url_for('index'))
        
        # Check if user owns this booking or is admin
        if current_user.is_authenticated:
            if not current_user.is_admin and booking.get('user_id') != str(current_user.id):
                flash('Access denied', 'error')
                return redirect(url_for('index'))
        else:
            flash('Please login to view booking', 'error')
            return redirect(url_for('login'))
        
        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(booking_id)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        # Save QR to BytesIO
        qr_buffer = BytesIO()
        qr_img.save(qr_buffer, format='PNG')
        qr_buffer.seek(0)
        qr_base64 = qr_buffer.getvalue()
        
        return render_template('booking_confirmation.html', booking=booking, qr_code=qr_base64)
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/download_ticket/<booking_id>')
def download_ticket(booking_id):
    try:
        booking = bookings_collection.find_one({'booking_id': booking_id})
        if not booking:
            flash('Booking not found', 'error')
            return redirect(url_for('index'))
        
        # Check permission
        if current_user.is_authenticated:
            if not current_user.is_admin and booking.get('user_id') != str(current_user.id):
                flash('Access denied', 'error')
                return redirect(url_for('index'))
        
        # Generate PDF
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        
        # Ticket content
        p.setFont("Helvetica-Bold", 24)
        p.drawString(100, 700, "MOVIE TICKET")
        
        p.setFont("Helvetica", 12)
        p.drawString(100, 660, f"Booking ID: {booking['booking_id']}")
        p.drawString(100, 640, f"Movie: {booking['movie_title']}")
        p.drawString(100, 620, f"Date: {booking['show_date']}")
        p.drawString(100, 600, f"Time: {booking['show_time']}")
        p.drawString(100, 580, f"Seats: {', '.join(booking['seats'])}")
        p.drawString(100, 560, f"Tickets: {booking['seat_count']}")
        p.drawString(100, 540, f"Total Amount: Rs. {booking['total_amount']}")
        p.drawString(100, 520, f"Status: {booking['status'].upper()}")
        
        p.showPage()
        p.save()
        
        buffer.seek(0)
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f'ticket_{booking_id}.pdf',
            mimetype='application/pdf'
        )
    except Exception as e:
        flash(f'Error generating ticket: {str(e)}', 'error')
        return redirect(url_for('index'))

# User Dashboard Routes
@app.route('/dashboard')
@login_required
def user_dashboard():
    user_bookings = list(bookings_collection.find({'user_id': str(current_user.id)}).sort('created_at', -1))
    
    # Calculate statistics
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
        
        # Update booking status
        bookings_collection.update_one(
            {'booking_id': booking_id},
            {'$set': {'status': 'cancelled', 'cancelled_at': datetime.now()}}
        )
        
        # Release seats
        movie_id = booking.get('movie_id')
        show_date = booking.get('show_date')
        show_time = booking.get('show_time')
        seats = booking.get('seats', [])
        
        movie = movies_collection.find_one({'_id': ObjectId(movie_id)})
        if movie:
            booked_seats = movie.get('booked_seats', {}).get(f"{show_date}_{show_time}", [])
            updated_seats = [s for s in booked_seats if s not in seats]
            movies_collection.update_one(
                {'_id': ObjectId(movie_id)},
                {'$set': {f'booked_seats.{show_date}_{show_time}': updated_seats}}
            )
        
        flash('Booking cancelled successfully', 'success')
        return redirect(url_for('user_dashboard'))
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
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

# API Routes
@app.route('/api/get_booked_seats/<movie_id>/<show_date>/<show_time>')
def get_booked_seats(movie_id, show_date, show_time):
    try:
        movie = movies_collection.find_one({'_id': ObjectId(movie_id)})
        if not movie:
            return jsonify({'seats': [])
        
        booked_seats = movie.get('booked_seats', {}).get(f"{show_date}_{show_time}", [])
        return jsonify({'seats': booked_seats})
    except:
        return jsonify({'seats': []})

# Error Handlers
@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

# Initialize default admin
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
