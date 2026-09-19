import db

def show_table_definition():
    conn = db.get_connection()
    cursor = conn.cursor()
    # Query the sqlite_schema to get the original CREATE TABLE statement
    cursor.execute("SELECT sql FROM sqlite_schema WHERE name='savings';")
    row = cursor.fetchone()
    
    if row:
        print("Original Table Definition:")
        print(row[0])
    else:
        print("Table 'savings' not found.")

show_table_definition()