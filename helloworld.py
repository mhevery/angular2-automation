import webapp2
import cgi
import json

from google.appengine.api import users
from google.appengine.ext import ndb
from google.appengine.api import urlfetch


class AuthToken(ndb.Model):
  service = ndb.StringProperty(indexed=True)
  username = ndb.StringProperty(indexed=True)
  token = ndb.StringProperty(indexed=False)
  
  @classmethod
  def forService(cls, service, username):
    auth = AuthToken.query().filter(AuthToken.service == service and AuthToken.username == username).get();
    if (auth is None):
      auth = AuthToken(service=service, username=username, token="")
      auth.put()
      return None
    else:
      return auth.token

  

class Audit(ndb.Model):
  date = ndb.DateTimeProperty(auto_now_add=True)
  event = ndb.StringProperty(indexed=False)
  delivery = ndb.StringProperty(indexed=False)
  body = ndb.StringProperty(indexed=False)
  

class MainPage(webapp2.RequestHandler):
  def get(self):
    user = users.get_current_user()

    if user:
      self.response.headers['Content-Type'] = 'text/plain'
      self.response.out.write('Hello, ' + user.nickname())
    else:
      self.redirect(users.create_login_url(self.request.uri))


class WebHookPage(webapp2.RequestHandler):
  def urlMethod(self, method, url):
    fullUrl = "https://api.github.com/repos/angular/angular/" + url;
    self.response.out.write(method)
    self.response.out.write(' ')
    self.response.out.write(fullUrl)
    self.response.out.write(' => ')
    response = urlfetch.Fetch(fullUrl, method = method, headers = {"Authorization": "token " + self.token})
    self.response.out.write(response.status_code)
    self.response.out.write('\n')
    return response
  
  def urlGET(self, url):
    return self.urlMethod(urlfetch.GET, url);
    
  def urlDELETE(self, url):
    return self.urlMethod(urlfetch.DELETE, url);
  
  def get(self):
    AuthToken.forService('github')
    self.response.headers['Content-Type'] = 'text/plain'
    self.response.out.write('Hello WebHook!')
      
  def post(self):
    event = self.request.headers["X-Github-Event"],
    if (event[0] != 'pull_request'):
      self.response.out.write('Not pull_request got ' + event[0])
      return
    audit = Audit(
      event = event[0],
      delivery = self.request.headers["X-GitHub-Delivery"],
      body = self.request.body)
    audit.put()
    data = json.loads(audit.body)
    self.token = AuthToken.forService('github', '*')
    if (self.token is None):
      self.response.out.write('No auth token')
      return
    pr_number = str(data['number'])
    result = self.urlGET('issues/' + pr_number + '/events')
    if result.status_code == 200:
      actionMerge = None
      for e in json.loads(result.content):
        if e['event'] == 'labeled' and e['label']['name'] == 'pr_action: merge' and e['actor']['login'] == 'mhevery':
          actionMerge = 'mhevery'
        if e['event'] == 'unlabeled' and e['label']['name'] == 'pr_action: merge':
          actionMerge = None
      self.response.out.write('Merge action? ' + str(actionMerge) + '\n')
      if (actionMerge != None): 
        result = self.urlDELETE('issues/' + pr_number + '/labels/pr_action:%20merge');



app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/web_hook', WebHookPage)
], debug=True)
