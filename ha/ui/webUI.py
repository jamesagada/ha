webLogging = False
webReload = False
blinkers = []

import json
import cherrypy
from cherrypy.lib import auth_basic
from ha import *
from ha.ui.webViews import *

# https://cherrypy.readthedocs.io/en/3.2.6/progguide/extending/customtools.html
# https://bitbucket.org/cherrypy/cherrypy/src/ea210e8ef58a3a6ca289a8564c389e38de13d3d5/cherrypy/lib/auth_basic.py?at=default&fileviewer=file-view-default

# user authentication
userFileName = keyDir+"users.json"
users = json.load(open(userFileName))
lanAddr = "192.168.1"
def validatePassword(realm, username, password):
    debug('debugWebAuth', "validatePassword", "ip:", cherrypy.request.remote.ip, "username:", username, "password:", password)
    # accept anything connecting from the LAN
    if ".".join(cherrypy.request.remote.ip.split(".")[0:3]) == lanAddr:
        debug('debugWebAuth', "validatePassword", "accepted")
        return True
    # validate the credentials
    if username in users and users[username] == password:
        debug('debugWebAuth', "validatePassword", "accepted")
        return True
    debug('debugWebAuth', "validatePassword", "rejected")
    return False
        
class WebRoot(object):
    def __init__(self, resources, cache, stateChangeEvent, resourceLock, pathDict):
        self.resources = resources
        self.cache = cache
        self.stateChangeEvent = stateChangeEvent
        self.resourceLock = resourceLock
        self.pathDict = pathDict

    # convert the path into a request parameter
    # this function gets called if cherrypy doesn't find a class method that matches the path    
    def _cp_dispatch(self, vpath):
        debug('debugWeb', "_cp_dispatch", "method:", cherrypy.request.method, "path:", vpath.__str__(), "params:", cherrypy.request.params.__str__())
        if len(vpath) == 1:
            # the path has one element, pop it off and return this root object
            # cherrypy will then call the index() 
            cherrypy.request.params['path'] = vpath.pop(0)
            return self
        # the request was for a file in the static/ directory, return the path
        return vpath

    # dispatch to the UI requested    
    @cherrypy.expose
    def index(self, path="", **params):
        debug('debugWeb', "index", cherrypy.request.method, "path:", path, "params:", params.__str__())
        try:
            return self.pathDict[path](**params)
        except KeyError:
            cherrypy.response.status = 404
            return path+" not found"

    # get or set a resource state
    @cherrypy.expose
    def cmd(self, resource=None, state=None):
        debug('debugWeb', "/cmd", cherrypy.request.method, resource, state)
        try:
            if resource == "resources":
                reply = ""
                for resource in self.resources.keys():
                    if resource != "states":
                        reply += resource+"\n"
                return reply
            else:
                if state:
                    self.resources.getRes(resource).setViewState(state, views)
                    time.sleep(1)   # hack
                return json.dumps({"state": self.resources.getRes(resource).getViewState(views)})
        except:
            return "Error"        

    # Return the value of a resource attribute
    @cherrypy.expose
    def value(self, resource=None, attr=None):
        debug('debugWeb', "/value", cherrypy.request.method, resource, attr)
        try:
            if resource:
                if attr:
                    return self.resources.getRes(resource).__getattribute__(attr).__str__()
                else:
                    return self.resources.getRes(resource).dict().__str__()
        except:
            return "Error"        

    # Update the states of all resources
    @cherrypy.expose
    def state(self, _=None):
        debug('debugWebUpdate', "/state", cherrypy.request.method)
        return self.updateStates(self.resources.getRes("states").getState())
        
    # Update the states of resources that have changed
    @cherrypy.expose
    def stateChange(self, _=None):
        debug('debugWebUpdate', "/stateChange", cherrypy.request.method)
        debug('debugInterrupt', "update", "event wait")
        self.stateChangeEvent.wait()
        debug('debugInterrupt', "update", "event clear")
        self.stateChangeEvent.clear()
        return self.updateStates(self.resources.getRes("states").getStateChange())

    # return the json to update the states of the specified collection of sensors
    def updateStates(self, resourceStates):
        if self.cache:
            cacheTime = self.cache.cacheTime
        else:
            cacheTime = 0
        updates = {"cacheTime": cacheTime}
        blinkerList = []
        for resource in resourceStates.keys():
            try:
                state = self.resources.getRes(resource).getState()
                resState = self.resources.getRes(resource).getViewState(views)
                resClass = self.resources.getRes(resource).type
                debug('debugWebUpdate', "/updateStates", resource, resClass, resState, state)
                if resClass in tempTypes:
                    updates[resource] = ("temp", resState)
                else:
                    if resClass not in staticTypes:
                        resClass += "_"+resState
                    updates[resource] = (resClass, resState)
                if (resource in blinkers) and (state > 0):
                    debug('debugWebBlink', "/updateStates", resource, resClass, resState, state)
                    blinkerList.append(resource)
            except:
                pass
        debug('debugWebBlink', "/updateStates", blinkerList)
        updates["blinkers"] = blinkerList
        return json.dumps(updates)
        
    # change the state of a control    
    @cherrypy.expose
    def submit(self, action=None, resource=None):
        debug('debugWeb', "/submit", cherrypy.request.method, action, resource)
        self.resources.getRes(resource).setViewState(action, views)
        reply = ""
        return reply

def webInit(resources, restCache, stateChangeEvent, resourceLock, httpPort=80, ssl=False, httpsPort=443, domain="", pathDict=None, baseDir="/", block=False):
    # set up the web server
    appConfig = {
        '/css': {
            'tools.staticdir.on': True,
            'tools.staticdir.root': os.path.join(baseDir, "static"),
            'tools.staticdir.dir': "css",
        },
        '/js': {
            'tools.staticdir.on': True,
            'tools.staticdir.root': os.path.join(baseDir, "static"),
            'tools.staticdir.dir': "js",
        },
        '/images': {
            'tools.staticdir.on': True,
            'tools.staticdir.root': os.path.join(baseDir, "static"),
            'tools.staticdir.dir': "images",
        },
        '/favicon.ico': {
            'tools.staticfile.on': True,
            'tools.staticfile.filename': os.path.join(baseDir, "static/favicon.ico"),
        },
    }
    if ssl:
        appConfig.update({
            '/': {
               'tools.auth_basic.on': True,
               'tools.auth_basic.realm': 'localhost',
               'tools.auth_basic.checkpassword': validatePassword
            }})

    # create a resource state sensor if there isn't one    
    try:
        stateResource = self.resources.getRes("states", dummy=False)
    except:
        debug('debugWeb', "created resource state sensor")
        stateResource = ResourceStateSensor("states", Interface("None"), resources=resources, event=stateChangeEvent)
        resources.addRes(stateResource)
        
    root = WebRoot(resources, restCache, stateChangeEvent, resourceLock, pathDict)
    cherrypy.tree.mount(root, "/", appConfig)
    cherrypy.server.unsubscribe()
    # http server for LAN access
    httpServer = cherrypy._cpserver.Server()
    httpServer.socket_port = httpPort
    httpServer._socket_host = "0.0.0.0"
    httpServer.max_request_body_size = 120 * 1024 # ~100kb
    httpServer.thread_pool = 30
    httpServer.subscribe()
    if ssl:
        # https server for external access
        httpsServer = cherrypy._cpserver.Server()
        httpsServer.socket_port = httpsPort
        httpsServer._socket_host = '0.0.0.0'
        httpsServer.max_request_body_size = 120 * 1024 # ~100kb
        httpsServer.thread_pool = 30
        httpsServer.ssl_module = 'pyopenssl'
        httpsServer.ssl_certificate = keyDir+domain+".crt"
        httpsServer.ssl_private_key = keyDir+domain+".key"
        httpsServer.subscribe()

    if not webLogging:
        access_log = cherrypy.log.access_log
        for handler in tuple(access_log.handlers):
            access_log.removeHandler(handler)
    if not webReload:
        cherrypy.engine.timeout_monitor.unsubscribe()
        cherrypy.engine.autoreload.unsubscribe()
    cherrypy.engine.start()
    if block:
        cherrypy.engine.block()
        