from functools import wraps

import jwt
from flask import jsonify, request

from Config.Config import KEY


def token_required(f):
    @wraps(f)
    def decorator(*args, **kwargs):

        token = None

        if 'Authorization' in request.headers:
            token = request.headers['Authorization']
            token = token.replace("Bearer ", "")

        if not token:
            return jsonify({'message': 'a valid token is missing'})

        try:
            data = jwt.decode(token, KEY, algorithms="HS256")
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Signature has expired'})
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Invalid token'})

        return f(data, *args, **kwargs)

    return decorator


def validate_token(token):
    try:
        jwt.decode(token, KEY, algorithms="HS256")
    except jwt.ExpiredSignatureError:
        return jsonify({'message': 'Signature has expired'})
    except jwt.InvalidTokenError:
        return jsonify({'message': 'Invalid token'})
    return jsonify({'message': 'Valid token'})
