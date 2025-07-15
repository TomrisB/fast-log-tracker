from fastapi import FastAPI, Request, HTTPException, Form
from pydantic import BaseModel, Field
from fastapi.responses import HTMLResponse, RedirectResponse # normalde JSON döner, html formatı için htmlresponse
from fastapi.templating import Jinja2Templates
import mysql.connector
import os
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level= logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s")

app = FastAPI()
logging.info("API is successfully started.")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # dynamic creation of path
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
LOG_FILE_PATH = os.path.join(BASE_DIR, "log_record.txt")


@app.get("/logs-panel", response_class=HTMLResponse)
def show_logs_panel(request: Request, start: str =None, end: str = None, source: str="db"):  # default source is db means it will record the log to db
    logging.info(f"/logs endpoint is called. Start: {start}, End: {end}")
    logs = []
    if start and end:
        if source == "db":
            try:
                connection = getconnection()
                cursor = connection.cursor()
                cursor.execute("SELECT * FROM logs WHERE timeStamp BETWEEN %s AND %s", (start,end))
                records = cursor.fetchall()
                connection.close()

                for row in records:
                    logs.append({
                            "source_ip": row[0],
                            "destination": row[1],
                            "timestamp": row[2].strftime("%Y-%m-%d %H:%M:%S")})
            except Exception as e:
                logging.error(f"DB Error: {e}")
        elif source == "txt":
            try:
                with open(LOG_FILE_PATH, "r", encoding= "utf-8") as file:
                    lines = file.readlines()  # list of lines
                    for line in lines: # [timestamp] IP: xxx -> yyy    structure of txt elements
                        if line.strip():
                            try:
                                timestamp_part = line.split("]")[0].strip("[")
                                ip_dest = line.split("]")[1].strip().replace("IP: ", "")
                                ip, dest = ip_dest.split(" -> ")
                                logs.append({
                                    "source_ip": ip,
                                    "destination": dest,
                                    "timestamp": timestamp_part})
                            except Exception as e:
                                logging.warning(f"Line could not be parsed: {line} | Error: {e}")
            except FileNotFoundError:
                logging.error("log_record file could not found.")
            except Exception as e:
                logging.exception("Error!")
    return templates.TemplateResponse("logs.html", {"request": request, "logs": logs})


def getconnection():
    try:
        conn = mysql.connector.connect(
            host = os.getenv("DB_HOST"),
            user = os.getenv("DB_USER"),
            password = os.getenv("DB_PASSWORD"),
            database = os.getenv("DB_NAME")  )
        logging.debug("Databse Connection is Succesfull.")
        return conn
    except Exception as e:
        logging.error(f"Could not connect to database: {e}")
        raise

class LogModel(BaseModel): 
    source_ip: str = Field(...,min_length = 7)
    destination: str
    timestamp: str
    record_type:str

def recordTxt(logg):
        with open(BASE_DIR+"/log_record.txt","a",encoding="utf-8") as file:
            file.write(f"\n[{logg.timestamp}] IP: {logg.source_ip} -> {logg.destination}")
        return logging.info("Log is succesfully recorded in file.")


def recordDB(logg):
    try:
        connection = getconnection()
        cursor = connection.cursor()
        sql = "INSERT INTO logs(sourceIP, destination, timeStamp) Values(%s,%s,%s)" 
        values = [logg.source_ip, logg.destination,logg.timestamp]
        cursor.execute(sql,values)
        connection.commit() 
    except mysql.connector.Error as err:
        logging.error("ERROR!:",err)
        raise
    finally:
        if connection.is_connected():
            connection.close() 
            logging.debug("DB connection is closed.")

@app.get("/")   
def read_root():
    return {"message": "API is working!"}  

@app.post("/log")
def add_log(log: LogModel): 
    try:
        if log.record_type == "db":
            recordDB(log)
        elif (log.record_type ==  "txt"):
            recordTxt(log)
        else:
            raise HTTPException(status_code=400, detail="invalid record type. (db/txt)")
        return {"message":"log is recorded", "type":log.record_type}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/logs")
def get_logs(start: str = None, end: str = None,source: str = "db"):
    logs = []
    if source == "db":
        try:
            connection = getconnection()
            cursor = connection.cursor()
        
            if (not start or not end):
                cursor.execute("SELECT * FROM logs")
            else:
                cursor.execute("SELECT * FROM logs WHERE timeStamp BETWEEN %s AND %s", (start, end,))
            
            records = cursor.fetchall()
            for row in records:
                logs.append({
                    "source_ip": row[0],
                    "destination": row[1],
                    "timestamp": row[2].strftime("%Y-%m-%d %H:%M:%S")})
            return {"logs": logs}
        except Exception as e:
            raise HTTPException(status_code= 500, detail = str(e))
        finally:
            if connection.is_connected():
                connection.close()
    elif source =="txt":
        start_dt =  datetime.strptime(start,"%Y-%m-%d %H:%M:%S") if start else None
        end_dt = datetime.strptime(end, "%Y-%m-%d %H:%M:%S") if end else None
        try:
            with open(LOG_FILE_PATH, "r", encoding= "utf-8") as file:
                lines = file.readlines()   # [timestamp] IP: xxx -> yyy
                for line in lines:
                    timestamp_str = line.split("]")[0].strip("[")
                    log_dt = datetime.strptime(timestamp_str,"%Y-%m-%d %H:%M:%S")
                    ip_dest = line.split("]")[1].strip().replace("IP: ", "")
                    ip, dest = ip_dest.split(" -> ")

                    if((not start_dt or not end_dt) or (start_dt <= log_dt <= end_dt)):
                        logs.append({
                    "source_ip": ip,
                    "destination": dest,
                    "timestamp": timestamp_str})
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error reading from file: {e}")



@app.get("/logs/{source_ip}")
def getLogBasedOnIP(source_ip: str, source:str="db"):
    logging.info(f"Query for: /log/{source_ip}")
    logs = []

    if source == "db":
        try:
            connection = getconnection()
            cursor = connection.cursor()
            cursor.execute("SELECT * FROM logs WHERE sourceIP = %s", (source_ip,))  
            records = cursor.fetchall()
            connection.close()

            if not records:
                logging.warning(f"Log not found for IP {source_ip} .")

            for row in records:
                logs.append({
                    "source_ip": row[0],
                    "destination": row[1],
                    "timestamp": row[2].strftime("%Y-%m-%d %H:%M:%S")
                })
            return {"logs": logs}
        except Exception as e:
            raise HTTPException(status_code=500, detail= str(e))
    elif(source =="txt"):
        try:
            with open(LOG_FILE_PATH,"r",encoding="utf-8") as file:
                lines = file.readlines()
                for line in lines:   # structure:   [timestamp] IP: xxx -> yyy
                    try:
                        if line.strip():
                            timestamp = line.split("]")[0].strip("[")
                            rest = line.split("]")[1].strip().replace("IP: ", "")
                            log_ip, dest = rest.split(" -> ")

                            if log_ip == source_ip:
                                logs.append({
                                    "source_ip": log_ip,
                                    "destination": dest,
                                    "timestamp": timestamp
                                })
                    except Exception as e:
                        logging.warning(f"Line parse error in TXT for IP filter: {line} | {e}")
            return {"logs": logs}
        except Exception as e:
            logging.warning(f"Log could not be read: {e}")
            raise HTTPException(status_code=500, detail="TXT log file could not be read.")


@app.get("/add-log",response_class=HTMLResponse)
def add_log_form(request: Request):
    return templates.TemplateResponse("add_log.html",{"request":request})

@app.post("/log-form")
def handle_log_form(
    source_ip: str = Form(...),
    destination: str = Form(...),
    timestamp: str = Form(...),
    record_type: str = Form(...)):
    
    log = LogModel(
        source_ip=source_ip,
        destination=destination,
        timestamp=timestamp,
        record_type=record_type
    )

    try:
        if record_type == "db":
            recordDB(log)
        elif record_type == "txt":
            recordTxt(log)
        else:
            raise HTTPException(status_code=400, detail="Invalid Record Type!")
        return RedirectResponse(url="/logs-panel", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




