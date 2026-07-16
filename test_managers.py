import logging
logging.basicConfig(level=logging.DEBUG)
import os, sys
sys.path.insert(0, os.path.join(os.getcwd(), 'sga_web'))

from dotenv import load_dotenv
load_dotenv('sga_web/.env')

from database_client import DatabaseClient
client = DatabaseClient()
client.connect()

print("Testing UserManager")
from user_manager import UserManager
UserManager('sga_web/users.json')

print("Testing SmartLabelManager")
from utils.smart_label_manager import SmartLabelManager
SmartLabelManager()

print("Testing HistoryManager")
from models import HistoryManager
HistoryManager()

print("Testing OrderStatusManager")
from models import OrderStatusManager
OrderStatusManager()

print("Testing TemplateManager")
from template_manager import TemplateManager
TemplateManager()

print("Testing GHSLabelGenerator")
from ghs_label_generator import GHSLabelGenerator
GHSLabelGenerator('unified_db')

print("ALL PASSED")
