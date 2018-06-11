import random
import string
import httplib2
import json
import requests
import os
import dicttoxml

from flask import Flask, render_template
from flask import request, redirect, url_for, make_response
from flask import jsonify, abort, flash, session as login_session

from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound

from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError

from database_setup import Base, Category, Item
from helper import get_user_id, create_user, get_all_categories
from helper import user_logged_in, allowed_file, generate_csrf_token
__author__ = 'Sai'
UPLOAD_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           'static/images/')

app = Flask(__name__)
CLIENT_ID = json.loads(open('client_secrets.json',
                            'r').read())['web']['client_id']

# Connect to Database and create database session
engine = create_engine('sqlite:///itemcatalog.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()


# Category JSON API Endpoint (GET Request)
@app.route('/catalog.json')
def catalog_json():
    categories = session.query(Category).all()
    batchs = [i.serialize for i in categories]

    for b in range(len(batchs)):
        item = [i.serialize for i in session.query(Item).filter_by
                (category_id=batchs[b]['id']).all()]
        batchs[b]['item'] = item

    return jsonify(Category=batchs)


# Category XML API Endpoint (GET Request)
@app.route('/catalog.xml')
def catalog_xml():
    categories = session.query(Category).all()
    batchs = [i.serialize for i in categories]

    for b in range(len(batchs)):
        item = [i.serialize for i in session.query(Item).filter_by
                (category_id=batchs[b]['id']).all()]
        batchs[b]['item'] = item

    response = make_response(dicttoxml.dicttoxml({'Category': batchs}))
    response.headers['Content-Type'] = 'application/xml'

    return response


# Login Page with oauth
@app.route('/login')
def user_login():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in range(32))
    login_session['state'] = state
    # return "The current session state is %s" % login_session['state']
    return render_template('login.html', STATE=state)


# google oauth connect
@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code, now compatible with Python3
    request.get_data()
    code = request.data.decode('utf-8')

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(json.dumps('Failed to upgrade.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = \
        'https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'\
        % access_token
    # Submit request, parse response - Python3 compatible
    h = httplib2.Http()
    response = h.request(url, 'GET')[1]
    str_response = response.decode('utf-8')
    result = json.loads(str_response)

    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(json.dumps("ID doesn't match"), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(json.dumps(" client ID does not match."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_access_token = login_session.get('access_token')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_access_token is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps('user is already connected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    # see if user exists, if it doesn't make a new one
    user_id = get_user_id(login_session['email'])
    if not user_id:
        user_id = create_user(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius: 150px;\
    -webkit-border-radius: 150px;-moz-border-radius: 150px;"> '
    flash("you are now logged in as %s" % login_session['username'])
    return output

# google oauth disconnect


@app.route('/gdisconnect')
def gdisconnect():

        # Only disconnect a connected user.
    access_token = login_session.get('access_token')
    if access_token is None:
        response = make_response(json.dumps('user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    url = 'https://accounts.google.com/o/oa\
           uth2/revoke?token=%s' % access_token
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    if result['status'] == '200':
        # Reset the user's sesson.
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']

        return redirect(url_for('index'))
    else:
        # For whatever reason, the given token was invalid.
        response = make_response(
            json.dumps('Failed to revoke token for given user.', 400))
        response.headers['Content-Type'] = 'application/json'
        return response


# Home Page for the application
@app.route('/')
def index():
    items = session.query(Item).order_by(desc(Item.created_date))
    return render_template('index.html', categories=get_all_categories(),
                           items=items, login_state=user_logged_in())


# Page shows items in a category
@app.route('/catalog/<category>/items')
def category_items(category):
    try:
        category_item = session.query(Category).filter_by(name=category).one()
        items = session.query(Item).filter_by(category=category_item)
        return render_template('category_items.html',
                               categories=get_all_categories(),
                               items=items, curr_cat=category,
                               login_state=user_logged_in())
    except NoResultFound:
        return redirect(url_for('index'))


# Gives description of the given item
@app.route('/catalog/<category>/<item>')
def item_description(category, item):
    try:
        category_item = session.query(Category).filter_by(name=category).one()
        item_content = session.query(Item).filter_by(category=category_item,
                                                     title=item).one()
        return render_template('item_description.html', item=item,
                               description=item_content.description,
                               item_id=item_content.id,
                               picture=item_content.picture,
                               login_state=user_logged_in())
    except NoResultFound:
        return redirect(url_for('index'))


# Add menu item
@app.route('/catalog/new', methods=['GET', 'POST'])
def item_new():
    if 'username' not in login_session:
        return redirect('/login')

    try:
        if request.method == 'POST' and request.form['title'] != "":
            image = request.files['image']
            image_filename = None
            if allowed_file(image.filename):
                image.save(os.path.join(app.config['UPLOAD_FOLDER'],
                           image.filename))
                image_filename = image.filename

            category = session.query(Category).filter_by(name=request.form
                                                         ['category']).one()
            if image_filename is None:
                item = Item(title=request.form['title'],
                            description=request.form['description'],
                            category=category)
            else:
                item = Item(title=request.form['title'],
                            description=request.form['description'],
                            category=category,
                            picture=image_filename)
            session.add(item)
            session.commit()
            return redirect(url_for('index'))
        else:
            categories = session.query(Category).all()
            return render_template('item_add.html',
                                   categories=categories,
                                   login_state=user_logged_in())
    except NoResultFound:
        return redirect(url_for('index'))


# Edit menu item
@app.route('/catalog/<item_id>/edit', methods=['GET', 'POST'])
def item_edit(item_id):
    if 'username' not in login_session:
        return redirect('/login')

    try:
        item = session.query(Item).filter_by(id=item_id).one()
        if request.method == 'POST':
            item.title = request.form['title']
            item.description = request.form['description']
            item_category =\
                session.query(Category).filter_by(name=request.form
                                                  ['category']).one()
            item.category = item_category

            image = request.files['image']
            if allowed_file(image.filename):
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'],
                          item.picture))
                image.save(os.path.join(app.config['UPLOAD_FOLDER'],
                           image.filename))
                item.picture = image.filename

            session.commit()
            return redirect(url_for('index'))
        else:
            categories = session.query(Category).all()
            return render_template('item_edit.html', item=item,
                                   categories=categories,
                                   login_state=user_logged_in())
    except NoResultFound:
        return redirect(url_for('index'))


# Delete menu item
@app.route('/catalog/<item_id>/delete', methods=['GET', 'POST'])
def item_delete(item_id):
    if 'username' not in login_session:
        return redirect('/login')

    try:
        item = session.query(Item).filter_by(id=item_id).one()
        if request.method == 'POST':

            # test for csrf validity
            token = login_session.pop('csrf_token', None)
            if not token or token != request.form.get('csrf_token'):
                abort(403)
            else:
                session.delete(item)
                session.commit()
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'],
                          item.picture))
                return redirect(url_for('index'))
        else:
            return render_template('item_delete.html',
                                   item=item, login_state=user_logged_in())
    except NoResultFound:
        return redirect(url_for('index'))


# Helper functions

if __name__ == '__main__':
    app.secret_key = 'this_key_is_secret'
    app.config['UPLOAD_FOLDER'] = UPLOAD_PATH
    app.debug = True
    app.jinja_env.globals['csrf_token'] = generate_csrf_token
    app.run(host='0.0.0.0', port=5000)
