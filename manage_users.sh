#!/bin/bash
# manage_users.sh

echo "=== Dashboard User Management ==="
echo "1. Add new user"
echo "2. Change password"
echo "3. List all users"
echo "4. Delete user"
echo -n "Choose option: "
read option

case $option in
    1)
        echo -n "Username: "
        read username
        echo -n "Password: "
        read -s password
        echo
        echo -n "Role (admin/user): "
        read role
        
        python3 -c "
import bcrypt
import json
import sys

def add_user(username, password, role='user'):
    try:
        with open('dashboard_users.json', 'r') as f:
            users = json.load(f)
    except:
        users = {}
    
    if username in users:
        return False, 'User already exists'
    
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    users[username] = {
        'password_hash': password_hash,
        'role': role,
        'created_at': '2024-01-01T00:00:00'
    }
    
    with open('dashboard_users.json', 'w') as f:
        json.dump(users, f, indent=2)
    
    return True, 'User created'

success, msg = add_user('$username', '$password', '$role')
print(msg)
"
        ;;
    2)
        echo -n "Username: "
        read username
        echo -n "New password: "
        read -s password
        echo
        
        python3 -c "
import bcrypt
import json
import sys

def change_password(username, new_password):
    try:
        with open('dashboard_users.json', 'r') as f:
            users = json.load(f)
    except:
        return False, 'Users file not found'
    
    if username not in users:
        return False, 'User not found'
    
    password_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    users[username]['password_hash'] = password_hash
    
    with open('dashboard_users.json', 'w') as f:
        json.dump(users, f, indent=2)
    
    return True, 'Password changed'

success, msg = change_password('$username', '$password')
print(msg)
"
        ;;
    3)
        python3 -c "
import json
try:
    with open('dashboard_users.json', 'r') as f:
        users = json.load(f)
    for user, info in users.items():
        print(f'{user} ({info[\"role\"]})')
except:
    print('No users found')
"
        ;;
    4)
        echo -n "Username to delete: "
        read username
        
        python3 -c "
import json
try:
    with open('dashboard_users.json', 'r') as f:
        users = json.load(f)
    
    if '$username' in users:
        del users['$username']
        with open('dashboard_users.json', 'w') as f:
            json.dump(users, f, indent=2)
        print('User deleted')
    else:
        print('User not found')
except:
    print('Error reading users file')
"
        ;;
    *)
        echo "Invalid option"
        ;;
esac