#!/usr/bin/env python3
from os import environ as env
import re, csv, sys, os, json
from collections.abc import Iterable
from http.server import ThreadingHTTPServer as HTTPServer, BaseHTTPRequestHandler as RequestHandler

dirname = os.path.dirname(__file__)

def marshal(self):
  if isinstance(self, list) or isinstance(self, dict):
    return self
  return list(self)

def isiterable(self):
  return isinstance(self, Iterable)

def split(path):
  parts = path.split('/')
  if parts[-1] == '':
    parts.pop()
  return parts
  
def match(pattern, text, flags=0):
  res = re.match(pattern, text, flags)
  if res is not None:
    yield res
    
class Raw:
  def __init__(self, text):
    self.text = text
    
  def __str__(self):
    return self.text
    
  def __call__(self, text, host):
    return self.text == text
    
class Param:
  def __init__(self, name):
    self.name = name
    
  def __str__(self):
    return self.name
    
  def __call__(self, text, host):
    host[self.name] = text
    return True
    
def parse_part(text):
  if re.match(r'\s', text):
    raise SyntaxError('')
  for res in match(r'^:(\S+)$', text):
    return Param(res[1])
  return Raw(text)
  
def parse(pattern):
  if isinstance(pattern, list):
    return pattern
  return [parse_part(part) for part in split(pattern)]
  
def tab(self):
  try:
    return len(self)
  except:
    return -1
  
def fuse(a, b):
  if tab(a) == tab(b):
    yield from zip(a, b)
      
class RESTHandler(RequestHandler):
  def do_GET(self):
    with self:
      if self('/models'):
        self.send(body=database.keys())
        
      if self('/models/:id'):
        key = self.params['id']
        if key in database:
          self.send(body=database[key])
        else:
          self.send(404)
    
  def do_POST(self):
    global last_id
    with self:
      if self('/models'):
        if self.read():
          if self.input is None:
            self.send(code=400)
          else:
            last_id += 1
            key = str(last_id)
            database[key] = self.input
            self.send(code=201, Location=key)
        else:
          self.send(code=400)
          
      if self('/models/:id'):
        self.send(code=405)
    
  def do_PUT(self):
    with self:
      if self('/models'):
        self.send(code=405)
        
      if self('/models/:id'):
        key = self.params['id']
        if self.read():
          if self.input is None:
            self.send(code=400)
          else:
            database[key] = self.input
            self.send(code=204, Location=key)
        else:
          self.send(code=400)
    
  def do_DELETE(self):
    with self:
      if self('/models'):
        self.send(code=405)
        
      if self('/models/:id'):
        key = self.params['id']
        if key in database:
          del database[key]
          self.send()
        else:
          self.send(404)
  
  def __enter__(self):
    self.parts = split(self.path)
    self.body = None
    
  def __exit__(self, *err):
    if self.parts is not None:
      self.send_response(400)  # Bad Request
      self.end_headers()
    elif self.body is None:
      try:
        self.end_headers()
      except AttributeError:
        pass # more info needed
    else:
      value = self.content_type
      if value == 'json':
        value = 'application/json'
      else:
        value = 'text/plain'
      self.send_header('Content-Type', value)
      self.send_header('Content-Length', len(self.body))
      self.end_headers()
      self.wfile.write(self.body)
  
  def __call__(self, schema):
    if self.parts is None:
      return False
    self.params = {}
    ret = False
    for pattern, part in fuse(parse(schema), self.parts):
      if not pattern(part, self.params):
        ret = False
        break
      
      ret = True
        
    if ret:
      self.parts = None
    return ret
    
  def send_headers(self, data):
    for key, val in data.items():
      self.send_header(key, val)
  
  def send(self, code=200, body=None, headers={}, **_headers):
    self.send_response(code)
    self.send_headers(headers)
    self.send_headers(_headers)
    if body is None:
      return False
    self.content_type = 'text'
    if isinstance(body, str):
      data = body
    elif isiterable(body):
      data = json.dumps(marshal(body))
      self.content_type = 'json'
    self.body = data.encode('utf_8')
    return True
    
  def read(self):
    try:
      size = int(self.headers.get('Content-Length'))
      if size == 0:
        return False
    except:
      self.send(411)
      return False
      
    try:
      data = self.rfile.read(size)
      if self.headers['Content-Type'] == 'application/json':
        self.input = json.loads(data);
      else:
        self.input = data
      return True
    except BlockingIOError:
      return False
    except JSONDecodeError:
      self.input = None
      return True
    
def resolve(*parts):
  return os.path.join(dirname, *parts)
    
print('Loading database...')
database = {}
last_id = -1
with open(resolve('Vehicles.csv'), newline='') as file:
  reader = csv.reader(file)
  header = next(reader)[1:]
  for item in reader:
    key = item[0]
    last_id = max(last_id, int(key))
    database[key] = dict(zip(header, item[1:]))
    
print('  done')
    
port = int(env.get('PORT', '8080'))
with HTTPServer(('', port), RESTHandler) as self:
  print('Server started at port %s...' % (self.server_port,))
  self.serve_forever()
  