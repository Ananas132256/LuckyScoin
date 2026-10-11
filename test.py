from db import DB

db = DB()
print("SC:", db.get_balance(123, "sc"))  
print("LC:", db.get_balance(123, "lc"))  