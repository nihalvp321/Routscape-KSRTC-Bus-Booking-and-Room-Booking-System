from flask import Flask, render_template, request, redirect, url_for, session, flash,jsonify
import sqlite3, os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from flask import make_response
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your_secret_key'
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def query_db(query, args=(), one=False):
    with sqlite3.connect('routescape.db') as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(query, args)
        rv = cur.fetchall()
        return (rv[0] if rv else None) if one else rv
    
def modify_db(query, args=()):
    with sqlite3.connect('routescape.db') as conn:
        cur = conn.cursor()
        cur.execute(query, args)
        conn.commit()
    
def nocache(view):
    @wraps(view)
    def no_cache_view(*args, **kwargs):
        response = make_response(view(*args, **kwargs))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    return no_cache_view

def init_db():
    with sqlite3.connect('routescape.db') as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT NOT NULL,
            profile_pic TEXT,
            address TEXT,
            state TEXT,
            pin TEXT,
            phone TEXT,
            gender TEXT
        )''')

#admin
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'Admin@123'

@app.route('/admin', methods=['GET', 'POST'])
@nocache
def adminlogin():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('adminhome'))
        else:
            flash('Invalid credentials', 'danger')
            return redirect(url_for('adminlogin'))  # <--- Redirect on failure
    return render_template('adminlogin.html')

@app.route('/adminhome')
@nocache
def adminhome():
    if not session.get('admin_logged_in'):
        return redirect(url_for('adminlogin'))

    conn = sqlite3.connect('routescape.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # User posts
    posts = query_db('''
        SELECT posts.id, posts.photo, posts.caption, posts.created_at, users.username, users.profile_pic 
        FROM posts 
        JOIN users ON posts.user_id = users.id 
        ORDER BY posts.created_at DESC
    ''')

    # Bus details
    cursor.execute("SELECT * FROM buses")
    buses_raw = cursor.fetchall()

    buses = []
    for bus in buses_raw:
        formatted_rate = round(float(bus[4]))
        total_seats = int(bus[5])
        image_path = bus[6].replace("static/", "") if bus[6] else None
        source_time = bus[7]
        destination_time = bus[8]
        buses.append((bus[0], bus[1], bus[2], bus[3], formatted_rate, total_seats, image_path, source_time, destination_time))

    # Booked seat map
    booked_seat_map = {}
    for bus in buses:
        bus_id = bus[0]
        cursor.execute("""
            SELECT bus_seats.seat_number, users.username, users.profile_pic, users.phone, users.email, users.address, 
                   buses.bus_number, buses.starting_point, buses.ending_point
            FROM bus_seats
            JOIN users ON bus_seats.user_id = users.id
            JOIN buses ON bus_seats.bus_id = buses.id
            WHERE bus_seats.bus_id = ? AND bus_seats.is_booked = 1
        """, (bus_id,))
        booked_seats = cursor.fetchall()

        seat_dict = {seat[0]: seat for seat in booked_seats}
        booked_seat_map[bus_id] = seat_dict

    # Fetch all room data (including available and booked rooms)
    # Fetch room data
    cursor.execute("SELECT * FROM room")
    rooms_data = cursor.fetchall()

    rooms = []
    for r in rooms_data:
     rooms.append({
        'id': r['id'],
        'room_name': r['room_name'],
        'type': r['type'],
        'description': r['description'],
        'price_per_night': r['price_per_night'],
        'max_occupancy': r['max_occupancy'],
        'image': r['image'],
        'is_available': r['is_available'],
        'booked_by': r['booked_by'] if r['is_available'] == 0 else 'Available'
    })

    # Fetch only booked room data for booking table (red boxes only)
    cursor.execute('''
     SELECT b.room_name, b.username, b.phone, b.date_from, b.date_to, 
           b.check_in_time, b.check_out_time
    FROM room_bookings b
    INNER JOIN room r ON b.room_name = r.room_name
    WHERE r.is_available = 0
''')
    bookings_data = cursor.fetchall()

    bookings = []
    for b in bookings_data:
     bookings.append({
        'room_name': b['room_name'],
        'username': b['username'],
        'phone': b['phone'],
        'date_from': b['date_from'],
        'date_to': b['date_to'],
        'check_in_time': b['check_in_time'],
        'check_out_time': b['check_out_time']
    })
 

    # -------------------------------
    # First: Fetch accessory bookings
    # -------------------------------
    cursor1 = conn.cursor()
    cursor1.execute("""
    SELECT a.name AS accessory_name, u.username, u.phone, u.profile_pic, ab.booking_date
    FROM accessory_bookings ab
    JOIN users u ON ab.user_id = u.id
    JOIN accessories a ON ab.accessory_id = a.id
    """)
    bookings_data = cursor1.fetchall()

    accessory_bookings = []
    for b in bookings_data:
     accessory_bookings.append({
        "accessory_name": b["accessory_name"],
        "username": b["username"],
        "phone": b["phone"],
        "profile_pic": b["profile_pic"],
        "booking_date": b["booking_date"]
    })


    # -------------------------------
    # Second: Fetch all accessories and their images
    # -------------------------------
    cursor2 = conn.cursor()
    cursor2.execute("SELECT * FROM accessories")
    accessories = cursor2.fetchall()

    accessory_list = []
    for acc in accessories:
        cursor2.execute("SELECT image_path FROM accessory_images WHERE accessory_id = ?", (acc["id"],))
        images = [img["image_path"] for img in cursor2.fetchall()]
        accessory_list.append({
            "id": acc["id"],
            "name": acc["name"],
            "description": acc["description"],
            "rate": acc["rate"],
            "total_items": acc["total_items"],
            "images": images
        })

    #feedbacks
    feedbacks = query_db('''
        SELECT f.rating, f.comment, f.submitted_at, u.username, u.profile_pic
        FROM feedback f
        JOIN users u ON f.user_id = u.id
        ORDER BY f.submitted_at DESC
        LIMIT 5
    ''')

    conn.close()


    return render_template('adminhome.html',
        posts=posts,
        buses=buses,
        booked_seat_map=booked_seat_map,
        rooms=rooms,
        bookings=bookings,
        accessories=accessory_list,
        accessory_bookings=accessory_bookings,
        feedbacks=feedbacks
    )

@app.route('/admin/add_bus', methods=['POST'])
def add_bus():
    bus_number = request.form['bus_number']
    starting_point = request.form['starting_point']
    ending_point = request.form['ending_point']
    source_time = request.form['source_time']
    destination_time = request.form['destination_time']
    rate = float(request.form['rate'])
    total_seats = int(request.form['total_seats'])

    bus_image = request.files.get('bus_image')
    image_path = None
    if bus_image and bus_image.filename != '':
        upload_folder = 'static/uploads/bus_images/'
        os.makedirs(upload_folder, exist_ok=True)
        filename = secure_filename(bus_image.filename)
        image_path = os.path.join(upload_folder, filename)
        bus_image.save(image_path)

    conn = sqlite3.connect('routescape.db')
    cursor = conn.cursor()

    # Insert the bus data into the buses table
    cursor.execute("""
        INSERT INTO buses (bus_number, starting_point, ending_point, rate, total_seats, image_path, source_time, destination_time)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (bus_number, starting_point, ending_point, rate, total_seats, image_path, source_time, destination_time))
    bus_id = cursor.lastrowid  # Get the id of the newly inserted bus

    # Insert seats into bus_seats table with is_booked as 0 and user_id as NULL
    for i in range(1, total_seats + 1):
        cursor.execute("""
            INSERT INTO bus_seats (bus_id, seat_number, is_booked, user_id)
            VALUES (?, ?, 0, NULL)
        """, (bus_id, f"S{i}"))

    conn.commit()
    conn.close()
    return redirect(url_for('adminhome'))

@app.route('/admin/edit_bus/<int:bus_id>', methods=['POST'])
def edit_bus(bus_id):
    bus_number = request.form['bus_number']
    starting_point = request.form['starting_point']
    ending_point = request.form['ending_point']
    total_seats = int(request.form['total_seats'])
    rate = float(request.form['rate'])
    source_time = request.form['source_time']
    destination_time = request.form['destination_time']

    bus_image = request.files.get('bus_image')
    image_path = None
    if bus_image and bus_image.filename != '':
        upload_folder = 'static/uploads/bus_images/'
        os.makedirs(upload_folder, exist_ok=True)
        filename = secure_filename(bus_image.filename)
        image_path = os.path.join(upload_folder, filename)
        bus_image.save(image_path)

    conn = sqlite3.connect('routescape.db')
    cursor = conn.cursor()

    if image_path:
        cursor.execute("""
            UPDATE buses 
            SET bus_number=?, starting_point=?, ending_point=?, total_seats=?, rate=?, image_path=?, source_time=?, destination_time=? 
            WHERE id=?
        """, (bus_number, starting_point, ending_point, total_seats, rate, image_path, source_time, destination_time, bus_id))
    else:
        cursor.execute("""
            UPDATE buses 
            SET bus_number=?, starting_point=?, ending_point=?, total_seats=?, rate=?, source_time=?, destination_time=?
            WHERE id=?
        """, (bus_number, starting_point, ending_point, total_seats, rate, source_time, destination_time, bus_id))

    conn.commit()
    conn.close()
    return redirect(url_for('adminhome'))

@app.route('/admin/delete_bus/<int:bus_id>', methods=['POST'])
def delete_bus(bus_id):
    conn = sqlite3.connect('routescape.db')
    cursor = conn.cursor()
    # Delete seats first (if any) associated with this bus
    cursor.execute("DELETE FROM bus_seats WHERE bus_id = ?", (bus_id,))
    # Delete the bus
    cursor.execute("DELETE FROM buses WHERE id = ?", (bus_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('adminhome'))

@app.route('/add_accessory', methods=['POST'])
def add_accessory():
    name = request.form['name']
    description = request.form['description']
    rate = request.form['rate']
    total_items=request.form['total_items']
    files = request.files.getlist('images')

    # Connect to the SQLite database
    conn = sqlite3.connect('routescape.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO accessories (name, description, rate, total_items) VALUES (?, ?, ?, ?)", (name, description, rate, total_items))
    accessory_id = cursor.lastrowid

    # Loop through the images and store them
    for file in files:
        if file.filename != '':
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            cursor.execute("INSERT INTO accessory_images (accessory_id, image_path) VALUES (?, ?)",
                           (accessory_id, f'uploads/{filename}'))  # Store the relative image path

    conn.commit()
    conn.close()
    return redirect(url_for('adminhome'))

@app.route('/edit_accessory/<int:accessory_id>', methods=['POST'])
def edit_accessory(accessory_id):
    name = request.form['name']
    description = request.form['description']
    rate = request.form['rate']
    total_items=request.form['total_items']
    files = request.files.getlist('images')

    conn = sqlite3.connect('routescape.db')
    cursor = conn.cursor()

    # Update the accessory details in the accessories table
    cursor.execute("""
        UPDATE accessories
        SET name = ?, description = ?, rate = ?, total_items=?
        WHERE id = ?
    """, (name, description, rate, total_items, accessory_id))

    # Handle image uploads
    for file in files:
        if file.filename != '':
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            # Insert the new image into the accessory_images table
            cursor.execute("""
                INSERT INTO accessory_images (accessory_id, image_path)
                VALUES (?, ?)
            """, (accessory_id, f'uploads/accessories/{filename}'))

    conn.commit()
    conn.close()

    return redirect(url_for('adminhome'))


@app.route('/delete_accessory/<int:accessory_id>', methods=['POST'])
def delete_accessory(accessory_id):
    conn = sqlite3.connect('routescape.db')
    conn.row_factory = sqlite3.Row  # Enable name-based access to columns
    cursor = conn.cursor()

    # Delete accessory bookings
    cursor.execute("DELETE FROM accessory_bookings WHERE accessory_id = ?", (accessory_id,))

    # Fetch and delete images
    cursor.execute("SELECT image_path FROM accessory_images WHERE accessory_id = ?", (accessory_id,))
    images = cursor.fetchall()
    for img in images:
        try:
            os.remove(os.path.join('static', img['image_path']))
        except:
            pass

    # Delete from accessory_images
    cursor.execute("DELETE FROM accessory_images WHERE accessory_id = ?", (accessory_id,))

    # Delete from accessories
    cursor.execute("DELETE FROM accessories WHERE id = ?", (accessory_id,))

    conn.commit()
    conn.close()
    return redirect(url_for('adminhome'))




@app.route('/adminlogout')
def adminlogout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('adminlogin'))


#user
@app.route('/')
def home():
    feedbacks = query_db('''
        SELECT f.rating, f.comment, f.submitted_at, u.username, u.profile_pic
        FROM feedback f
        JOIN users u ON f.user_id = u.id
        ORDER BY f.submitted_at DESC
        LIMIT 5
    ''')
    return render_template('main.html', feedbacks=feedbacks)


@app.route('/userregister', methods=['GET', 'POST'])
def userregister():
    if request.method == 'POST':
        data = request.form

        # Check password match
        if data['password'] != data['confirm_password']:
            flash("Passwords do not match", "danger")
            return render_template('userregister.html')

        # Hash password
        hashed_password = generate_password_hash(data['password'])

        # Default profile pic fallback
        default_pic = 'noprofile.png'

        try:
            with sqlite3.connect('routescape.db') as conn:
                cur = conn.cursor()
                cur.execute('''
                    INSERT INTO users (username, password, email, profile_pic, address, state, pin, phone, gender)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    data['username'], hashed_password, data['email'], default_pic,
                    data['address'], data['state'], data['pin'], data['phone'], data['gender']
                ))
                conn.commit()
                flash('Registration successful!', 'success')
                return redirect(url_for('userlogin'))
        except sqlite3.IntegrityError:
            flash('Username already exists.', 'danger')

    return render_template('userregister.html')


@app.route('/userlogin', methods=['GET', 'POST'])
def userlogin():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        with sqlite3.connect('routescape.db') as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute('SELECT * FROM users WHERE username = ?', (username,))
            user = cur.fetchone()
            
            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['phone'] = user['phone']
                return redirect(url_for('userhome'))  # 👈 No flash here
            else:
                flash('Invalid credentials', 'danger')
                return redirect(url_for('userlogin'))
    
    return render_template('userlogin.html')
    
@app.route('/userhome', methods=['GET', 'POST'])
@nocache
def userhome():
    if 'username' not in session:
        return redirect(url_for('userlogin'))

    user_data = query_db("SELECT id, username, profile_pic FROM users WHERE username = ?", (session['username'],), one=True)
    if not user_data:
        flash("User not found. Please log in again.", "error")
        return redirect(url_for('userlogin'))

    user_id = user_data['id']
    username = user_data['username']
    profile_pic = user_data['profile_pic'] or 'noprofile.png'

    uploads_path = os.path.join('static', 'uploads', profile_pic)
    if not os.path.exists(uploads_path):
        profile_pic = 'noprofile.png'

    posts = query_db('''SELECT posts.id, posts.photo, posts.caption, posts.created_at,
                        users.username, users.profile_pic
                        FROM posts JOIN users ON posts.user_id = users.id
                        WHERE posts.user_id = ? ORDER BY posts.created_at DESC''', (user_id,)) or []

    all_posts = query_db('''SELECT posts.id, posts.photo, posts.caption, posts.created_at,
                             users.username, users.profile_pic
                             FROM posts JOIN users ON posts.user_id = users.id
                             ORDER BY posts.created_at DESC''') or []

    buses = query_db('''SELECT b.*, 
                        (SELECT COUNT(*) FROM bus_seats bs WHERE bs.bus_id = b.id AND bs.is_booked = 0) AS available_seats
                        FROM buses b''')

    # Room type filtering
    room_type = ""
    rooms = query_db("SELECT * FROM room")  # Load all rooms initially

    if request.method == 'POST':
     room_type = request.form.get('room_type', '')
     if room_type and room_type != 'All':  # If not 'All', filter by room type
        rooms = query_db("SELECT * FROM room WHERE type = ?", (room_type,))

    # Pass room images from the 'room' table (comma-separated image paths)
    # Fetch room images as a list from the database
    room_images = {}
    for room in rooms:
    # Ensure 'image' field is a string and split by commas
     images = room['image'].split(',') if room['image'] else []
     room_images[room['id']] = images  # Store as list of image paths

    conn = sqlite3.connect('routescape.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()


# Second: Fetch all accessories and their images
    # -------------------------------
    cursor2 = conn.cursor()
    cursor2.execute("SELECT * FROM accessories")
    accessories = cursor2.fetchall()

    accessory_list = []
    for acc in accessories:
        cursor2.execute("SELECT image_path FROM accessory_images WHERE accessory_id = ?", (acc["id"],))
        images = [img["image_path"] for img in cursor2.fetchall()]
        accessory_list.append({
            "id": acc["id"],
            "name": acc["name"],
            "description": acc["description"],
            "rate": acc["rate"],
            "total_items": acc["total_items"],
            "images": images
        })

    conn.close()


    return render_template('userhome.html',
                           username=username,
                           profile_image=profile_pic,
                           posts=posts,
                           all_posts=all_posts,
                           buses=buses,
                           rooms=rooms,
                           room_type=room_type,
                           room_images=room_images,
                           accessories=accessory_list)  # Pass room images to the template


# ------------------- SEARCH ROOMS -------------------
@app.route('/search_rooms', methods=['POST'])
@nocache
def search_rooms():
    if 'username' not in session:
        return redirect(url_for('userlogin'))

    # Get search criteria
    room_type = request.form.get('room_type', '')
    date_from = request.form.get('date_from', '')
    date_to = request.form.get('date_to', '')
    checkin_time = request.form.get('checkin_time', '')
    checkout_time = request.form.get('checkout_time', '')

    # Adjust your query to handle these conditions for rooms
    query = "SELECT * FROM room WHERE is_available = 1"
    params = []

    # Add filters based on search criteria for rooms
    if room_type:
        query += " AND type = ?"
        params.append(room_type)

    if date_from and date_to:
        query += " AND available_from <= ? AND available_to >= ?"
        params.extend([date_from, date_to])

    if checkin_time and checkout_time:
        query += " AND checkin_time <= ? AND checkout_time >= ?"
        params.extend([checkin_time, checkout_time])

    rooms = query_db(query, tuple(params))

    return render_template('userhome.html', rooms=rooms, date_from=date_from, date_to=date_to, checkin_time=checkin_time, checkout_time=checkout_time)

# ------------------- BOOK ROOM -------------------
@app.route('/book_room', methods=['POST'])
@nocache
def book_room():
    if 'username' not in session:
        return redirect(url_for('userlogin'))

    try:
        room_name = request.form['room_name']
        room_type = request.form['room_type']
        date_from = request.form['date_from']
        date_to = request.form['date_to']
        checkin_time = request.form['check_in']
        checkout_time = request.form['check_out']
        username = session['username']
        phone = request.form['phone']  # From input form

        conn = sqlite3.connect('routescape.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Step 1: Check for existing booking
        cursor.execute('''
            SELECT * FROM room_bookings
            WHERE room_name = ? AND username = ? AND date_from = ? AND date_to = ?
        ''', (room_name, username, date_from, date_to))

        existing_booking = cursor.fetchone()
        if existing_booking:
            conn.close()
            return jsonify({"success": False, "message": "You already booked this room for these dates."})

        # Step 2: Proceed to insert if not already booked
        cursor.execute('''
            INSERT INTO room_bookings (room_name, username, phone, date_from, date_to, check_in_time, check_out_time)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (room_name, username, phone, date_from, date_to, checkin_time, checkout_time))

        cursor.execute("UPDATE room SET is_available = 0, booked_by = ? WHERE room_name = ?", (username, room_name))

        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Room booked successfully!"})

    except Exception as e:
        conn.close()
        return jsonify({"success": False, "message": f"Error booking room: {str(e)}"})

    
# ------------------------------
# 2. Fetch seats for a specific bus
# ------------------------------
@app.route('/get_seats/<int:bus_id>')
def get_seats(bus_id):
    seats = query_db('''
    SELECT id, seat_number, is_booked FROM bus_seats
    WHERE bus_id = ?
    ORDER BY CAST(seat_number AS INTEGER)
    ''', (bus_id,))

    return jsonify([dict(seat) for seat in seats])

# 3. Book a seat (Dummy Payment)
@app.route('/book_seat/<int:seat_id>/<int:bus_id>', methods=['POST'])
def book_seat(seat_id, bus_id):
    if 'username' not in session:
        return jsonify({'status': 'error', 'message': 'User not logged in'})

    seat = query_db("SELECT * FROM bus_seats WHERE id = ?", (seat_id,), one=True)
    if not seat or seat['is_booked'] == 1:
        return jsonify({'status': 'error', 'message': 'Seat already booked'})

    booked_by = session['username']
    
    # Fetch the user ID from session
    user_data = query_db("SELECT id FROM users WHERE username = ?", (booked_by,), one=True)
    if not user_data:
        return jsonify({'status': 'error', 'message': 'User not found in DB'})

    user_id = user_data['id']

    # Update the seat as booked and assign user_id
    modify_db('''
        UPDATE bus_seats 
        SET is_booked = 1, booked_by = ?, user_id = ? 
        WHERE id = ?
    ''', (booked_by, user_id, seat_id))

    return jsonify({'status': 'success', 'message': f'Seat booked successfully by {booked_by}!'})



# Route to fetch rate and bus number for payment modal
@app.route('/get_bus_rate/<int:bus_id>')
def get_bus_rate(bus_id):
    bus = query_db("SELECT bus_number, rate, source_time, destination_time FROM buses WHERE id = ?", (bus_id,), one=True)
    if not bus:
        return jsonify({'error': 'Bus not found'}), 404
    return jsonify(dict(bus))


@app.route('/update_post/<int:post_id>', methods=['GET', 'POST'])
def update_post(post_id):
    if 'username' not in session:
        return redirect(url_for('userlogin'))

    if request.method == 'POST':
        new_caption = request.form['caption']
        with sqlite3.connect('routescape.db') as conn:
            cur = conn.cursor()
            cur.execute("UPDATE posts SET caption = ? WHERE id = ?", (new_caption, post_id))
            conn.commit()
        flash("Post updated successfully!", "success")
        return redirect(url_for('userhome'))

    # No need to render update_post.html anymore
    return redirect(url_for('userhome'))

@app.route('/delete_post/<int:post_id>')
def delete_post(post_id):
    if 'username' not in session:
        return redirect(url_for('userlogin'))

    with sqlite3.connect('routescape.db') as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM posts WHERE id = ?", (post_id,))
        conn.commit()
    flash("Post deleted successfully!", "success")
    return redirect(url_for('userhome'))


@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    if 'username' not in session:
        flash("You need to log in to submit feedback!", "danger")
        return redirect(url_for('userlogin'))

    user_data = query_db("SELECT id FROM users WHERE username = ?", (session['username'],), one=True)
    if not user_data:
        flash("User not found.", "danger")
        return redirect(url_for('userlogin'))

    user_id = user_data['id']
    rating = request.form.get('rating')
    comment = request.form.get('comment')

    if not rating or not comment:
        flash("Rating and comment are required.", "danger")
        return redirect(url_for('userhome'))

    try:
        rating = int(rating)
        if rating < 1 or rating > 5:
            raise ValueError("Rating out of bounds")
    except:
        flash("Invalid rating. Please select a rating between 1 and 5.", "danger")
        return redirect(url_for('userhome'))

    with sqlite3.connect('routescape.db') as conn:
        cur = conn.cursor()
        cur.execute('''INSERT INTO feedback (user_id, rating, comment, submitted_at)
                       VALUES (?, ?, ?, ?)''', (user_id, rating, comment, datetime.now()))
        conn.commit()

    flash("Thank you for your feedback!", "success")
    return redirect(url_for('userhome'))




@app.route('/profile')
def profile():
    if 'username' not in session:
        return redirect(url_for('userlogin'))

    user = query_db("SELECT * FROM users WHERE username = ?", (session['username'],), one=True)
    if not user:
        flash("User not found")
        return redirect(url_for('userlogin'))

    profile_pic = user[4] if user[4] else 'noprofile.png'
    return render_template(
    'profile.html',
    user={
        'username': user[1], 'email': user[3], 'address': user[5], 'state': user[6],
        'pin': user[7], 'phone': user[8], 'gender': user[9]
    },
    profile_pic=profile_pic,
    current_time=datetime.now().timestamp()
)

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'username' not in session:
        return redirect(url_for('userlogin'))

    data = (
        request.form['username'],
        request.form['email'],
        request.form.get('address', ''),
        request.form.get('state', ''),
        request.form.get('pin', ''),
        request.form.get('phone', ''),
        request.form.get('gender', ''),
        session['username']
    )

    query_db("""UPDATE users SET username = ?, email = ?, address = ?, state = ?, 
                pin = ?, phone = ?, gender = ? WHERE username = ?""", data)
    session['username'] = request.form['username']
    flash("Profile updated successfully!")
    return redirect(url_for('profile'))

@app.route('/update_profile_pic', methods=['POST'])
def update_profile_pic():
    if 'username' not in session:
        return redirect(url_for('userlogin'))

    file = request.files['profile_pic']
    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        query_db("UPDATE users SET profile_pic = ? WHERE username = ?", (filename, session['username']))
        flash("Profile picture updated.")
    return redirect(url_for('profile'))

@app.route('/delete_profile_pic', methods=['POST'])
def delete_profile_pic():
    if 'username' not in session:
        return redirect(url_for('userlogin'))

    query_db("UPDATE users SET profile_pic = NULL WHERE username = ?", (session['username'],))
    flash("Profile picture removed.")
    return redirect(url_for('profile'))


@app.route('/upload_post', methods=['POST'])
def upload_post():
    if 'username' not in session:
        flash("You need to log in to post!", "danger")
        return redirect(url_for('userlogin'))

    # Get user info from session
    user_data = query_db("SELECT id FROM users WHERE username = ?", (session['username'],), one=True)
    if not user_data:
        flash("User not found.", "danger")
        return redirect(url_for('userlogin'))

    user_id = user_data['id']  # Get the user_id

    # Get the uploaded file and caption
    file = request.files['media']
    caption = request.form['caption']

    if not caption or not file:
        flash("Caption and media are required.", "danger")
        return redirect(url_for('userhome'))

    # Secure the filename and save the file
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    # Save post details to database using user_id
    with sqlite3.connect('routescape.db') as conn:
        cur = conn.cursor()
        cur.execute('''INSERT INTO posts (user_id, photo, caption, created_at)
                       VALUES (?, ?, ?, ?)''', (user_id, filename, caption, datetime.now()))
        conn.commit()

    flash("Your post has been uploaded!", "success")
    return redirect(url_for('userhome'))


@app.route('/book_accessory/<int:accessory_id>', methods=['POST'])
def book_accessory(accessory_id):
    if 'user_id' not in session:
        flash('Please log in to book accessories.')
        return redirect(url_for('userlogin'))

    user_id = session['user_id']
    username = session['username']
    phone = session['phone']
    booking_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = sqlite3.connect('routescape.db')
    conn.row_factory = sqlite3.Row  # This allows you to access columns by name
    cursor = conn.cursor()

    # Check current availability and join with accessory_images table to get the image
    cursor.execute('''
        SELECT a.*, ai.image_path
        FROM accessories a
        LEFT JOIN accessory_images ai ON a.id = ai.accessory_id
        WHERE a.id = ?
    ''', (accessory_id,))
    
    accessory = cursor.fetchone()

    # Check if accessory is found and print to debug
    if not accessory:
        flash('Accessory not found.')
        conn.close()
        return redirect(url_for('userhome'))

    try:
        # Accessory details using column names
        available_items = accessory['total_items']
    except KeyError:
        flash('Accessory data is incomplete or corrupted.')
        conn.close()
        return redirect(url_for('userhome'))

    if available_items <= 0:
        flash('This accessory is currently not available.')
        conn.close()
        return redirect(url_for('userhome'))

    # Book the accessory
    cursor.execute(''' 
        INSERT INTO accessory_bookings (accessory_id, user_id, username, phone, booking_date)
        VALUES (?, ?, ?, ?, ?)
    ''', (accessory_id, user_id, username, phone, booking_date))

    # Reduce available item count
    cursor.execute('''
        UPDATE accessories
        SET total_items = total_items - 1
        WHERE id = ?
    ''', (accessory_id,))

    conn.commit()
    conn.close()

    # Flash success message
    flash('Accessory booked successfully! You can download your receipt below.')

    return redirect(url_for('userhome'))


@app.route('/userlogout')
def userlogout():
    session.pop('username', None)
    return redirect(url_for('userlogin'))

#room manager
# Hardcoded credentials
ROOM_MANAGER_USERNAME = 'manager123'
ROOM_MANAGER_PASSWORD = 'pass1234'

@app.route('/roommanager', methods=['GET', 'POST'])
@nocache
def roommanager_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == ROOM_MANAGER_USERNAME and password == ROOM_MANAGER_PASSWORD:
            session['roommanager_logged_in'] = True
            return redirect(url_for('roommanager_dashboard'))
        else:
            flash('Invalid credentials', 'danger')
    
    return render_template('roommanager_login.html')

@app.route('/roommanager_dashboard')
@nocache
def roommanager_dashboard():
    if not session.get('roommanager_logged_in'):
        return redirect(url_for('roommanager_login'))

    rooms_data = query_db('SELECT * FROM room')

    rooms = []
    for r in rooms_data:
        rooms.append({
            'id': r['id'],
            'room_name': r['room_name'],
            'type': r['type'],
            'description': r['description'],
            'price_per_night': r['price_per_night'],
            'max_occupancy': r['max_occupancy'],
            'image': r['image'],
            'is_available': r['is_available'],
            'booked_by': r['booked_by'] if r['is_available'] == 0 else 'Not Booked'
        })

    # ✅ Only include bookings with existing room entries
    bookings_data = query_db('''
        SELECT b.room_name, b.username, b.phone, b.date_from, b.date_to, 
           b.check_in_time, b.check_out_time
    FROM room_bookings b
    INNER JOIN room r ON b.room_name = r.room_name
    WHERE r.is_available = 0
    ''')

    bookings = []
    for b in bookings_data:
        bookings.append({
            'room_name': b['room_name'],
            'username': b['username'],
            'phone': b['phone'],
            'date_from': b['date_from'],
            'date_to': b['date_to'],
            'check_in_time': b['check_in_time'],
            'check_out_time': b['check_out_time']
        })

    return render_template('roommanager_dashboard.html', rooms=rooms, bookings=bookings)

@app.route('/add_room', methods=['POST'])
def add_room():
    room_name = request.form['room_name']
    room_type = request.form['type']
    description = request.form['description']
    price = request.form['price']
    occupancy = request.form['occupancy']

    images = request.files.getlist('images')
    image_paths = []

    upload_folder = os.path.join(app.root_path, 'static', 'room_images')
    os.makedirs(upload_folder, exist_ok=True)

    for image in images:
        if image.filename:
            filename = secure_filename(image.filename)
            filepath = os.path.join(upload_folder, filename)
            image.save(filepath)
            image_paths.append(f'room_images/{filename}')

    image_string = ','.join(image_paths)

    try:
        query_db('''
            INSERT INTO room (room_name, type, description, price_per_night, max_occupancy, image)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (room_name, room_type, description, price, occupancy, image_string))
        flash("Room added successfully!", "success")
    except sqlite3.IntegrityError as e:
        flash("Room name must be unique or there was a database error.", "error")
        print(e)

    return redirect(url_for('roommanager_dashboard'))

@app.route('/get_rooms')
def get_rooms():
    rooms = query_db('SELECT * FROM room')
    return jsonify({'rooms': rooms})

@app.route('/delete_room/<int:room_id>')
def delete_room(room_id):
    # Optional: remove image files here too if desired
    query_db('DELETE FROM room WHERE id = ?', (room_id,))
    flash('Room deleted successfully!', 'success')
    return redirect(url_for('roommanager_dashboard'))

@app.route('/update_room/<int:room_id>')
def update_room_form(room_id):
    room = query_db('SELECT * FROM room WHERE id = ?', (room_id,), one=True)
    if not room:
        flash('Room not found', 'danger')
        return redirect(url_for('roommanager_dashboard'))

    # Pass the selected room ID as a query parameter so the dashboard can show the update form for it
    return redirect(url_for('roommanager_dashboard', update_room_id=room_id))

@app.route('/update_room/<int:room_id>', methods=['POST'])
def update_room(room_id):
    room_name = request.form['room_name']
    room_type = request.form['type']
    description = request.form['description']
    price = request.form['price']
    occupancy = request.form['occupancy']
    is_available = int(request.form.get('is_available'))

    # 🛠️ Fix: Set 'booked_by' based on room availability
    if is_available == 1:
        booked_by = 'Not Booked'
    else:
        booked_by = request.form.get('booked_by', '').strip()

    images = request.files.getlist('images')
    image_paths = []
    image_string = None

    if images and any(img.filename for img in images):
        upload_folder = os.path.join(app.root_path, 'static', 'room_images')
        os.makedirs(upload_folder, exist_ok=True)

        for image in images:
            if image.filename:
                filename = secure_filename(image.filename)
                filepath = os.path.join(upload_folder, filename)
                image.save(filepath)
                image_paths.append(f'room_images/{filename}')

        image_string = ','.join(image_paths)

    if image_string:
        query_db(''' 
            UPDATE room 
            SET room_name=?, type=?, description=?, price_per_night=?, max_occupancy=?, image=?, is_available=?, booked_by=?
            WHERE id=? 
        ''', (room_name, room_type, description, price, occupancy, image_string, is_available, booked_by, room_id))
    else:
        query_db(''' 
            UPDATE room 
            SET room_name=?, type=?, description=?, price_per_night=?, max_occupancy=?, is_available=?, booked_by=?
            WHERE id=? 
        ''', (room_name, room_type, description, price, occupancy, is_available, booked_by, room_id))

    flash('Room updated successfully!', 'success')
    return redirect(url_for('roommanager_dashboard'))


@app.route('/roommanager_logout')
@nocache
def roommanager_logout():
    session.pop('roommanager_logged_in', None)
    return redirect(url_for('roommanager_login'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
