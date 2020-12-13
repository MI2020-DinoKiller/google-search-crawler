import os
import sys
import logging
import json
import pika


dataPath = os.path.dirname(os.path.abspath(__file__))

logging.info("正在分析 config.json 檔案...")
input_file = open(os.path.join(dataPath, 'config.json'))
CONFIG = json.load(input_file)
logging.info("分析完畢 config.json")

connection = pika.BlockingConnection(pika.ConnectionParameters(
    host=CONFIG["RABBITMQ"]["HOST"], heartbeat=0,))
channel = connection.channel()
channel.queue_declare(queue=CONFIG["RABBITMQ"]["QUEUE_SEARCH"], durable=True)
obj = {"searchText": sys.argv[1]}
channel.basic_publish(
    exchange='',
    routing_key=CONFIG["RABBITMQ"]["QUEUE_SEARCH"],
    body=json.dumps(obj),
    properties=pika.BasicProperties(delivery_mode=2)  # make message persistent
)