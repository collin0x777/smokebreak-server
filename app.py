import os
from twilio.rest import Client
from flask import Flask, request
import redis
import urllib.parse

app = Flask(__name__)

def log_request(phone_number):

    url = urllib.parse.urlparse(os.environ.get('REDISCLOUD_URL'))
    r = redis.Redis(host=url.hostname, port=url.port, password=url.password)

    maxPerDay = os.getenv('MAX_PER_DAY', 20)

    log_script = """
    local phoneKey = KEYS[1]
    local maxPerDay = ARGV[1]

    if redis.call('exists', phoneKey) == 1 then
        if tonumber(redis.call('get', phoneKey)) > maxPerDay then
            return 0
        end
        redis.call('incr', phoneKey)
        return 1
    else
        redis.call('set', phoneKey, 1)
        redis.call('expire', phoneKey, 86400)
        return 1
    end
    """

    return r.eval(log_script, 1, phone_number, maxPerDay)

def send_message(phone_number, message):
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    from_number = os.getenv('TWILIO_FROM_NUMBER')
    client = Client(account_sid, auth_token)

    result = client.messages.create(
        from_=from_number,
        body=message,
        to=phone_number,
    )

    print(result)

@app.route('/', methods=['POST'])
def result():
    json = request.json
    status = json['status']
    command = json['command']
    phone_number = json['phone']

    truncated_command = command[:20] + '...' if len(command) > 20 else command

    message = 'Command completed with exit code ' + str(status) + '.\n' + truncated_command

    if log_request(phone_number):
        send_message(phone_number, message)
        return 'OK'
    else:
        return 'Too many requests', 429