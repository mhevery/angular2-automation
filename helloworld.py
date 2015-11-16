import webapp2
import cgi
import json

from google.appengine.api import users
from google.appengine.ext import ndb
from google.appengine.api import urlfetch


class CoreTeamMember(ndb.Model):
  username = ndb.StringProperty(indexed=True)

  @classmethod
  def forUsername(cls, username):
    return CoreTeamMember.query().filter(CoreTeamMember.username == username).get();


class AuthToken(ndb.Model):
  service = ndb.StringProperty(indexed=True)
  token = ndb.StringProperty(indexed=True)
  
  @classmethod
  def forService(cls, service):
    auth = AuthToken.query().filter(AuthToken.service == service).get();
    if (auth is None):
      auth = AuthToken(service=service, token="-missing-")
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
  def urlMethod(self, method, token, url, payload):
    fullUrl = "https://api.github.com/repos/angular/angular/" + url;
    headers =  {"Authorization": "token " + token}
    if (payload != None):
      payload = json.dumps(payload)
    self.response.out.write(method)
    self.response.out.write(' ')
    self.response.out.write(fullUrl)
    self.response.out.write(' => ')
    response = urlfetch.Fetch(fullUrl, method = method, headers = headers, payload = payload)
    self.response.out.write(response.status_code)
    self.response.out.write('\n')
    return response
  
  def urlGET(self, token, url):
    return self.urlMethod(urlfetch.GET, token, url, None);
    
  def urlDELETE(self, token, url):
    return self.urlMethod(urlfetch.DELETE, token, url, None);
    
  def urlPOST(self, token, url, content):
    return self.urlMethod(urlfetch.POST, token, url, content);
    
  def urlPATCH(self, token, url, content):
    return self.urlMethod(urlfetch.PATCH, token, url, content);
    
  
  
  def get(self):
    AuthToken.forService('github')
    self.response.headers['Content-Type'] = 'text/plain'
    self.response.out.write('Hello WebHook!')
      
  def post(self):
    # labels applied by the onduty to automate merges
    merge_label = 'zomg_admin: do merge'
    merge_label_uri_esc = 'zomg_admin:%20do%20merge'

    if (CoreTeamMember.forUsername('*') == None):
      CoreTeamMember(username = '*').put()      
    event = self.request.headers["X-Github-Event"],
    if (event[0] != 'pull_request'):
      self.response.out.write('Not pull_request got ' + event[0])
      return
    data = json.loads(self.request.body)
    if (data['action'] != 'labeled'):
      return
    audit = Audit(
      event = event[0],
      delivery = self.request.headers["X-GitHub-Delivery"],
      body = self.request.body)
    audit.put()
    tokenComment = AuthToken.forService('github-comment')
    tokenPush = AuthToken.forService('github-push')
    if (tokenComment is None):
      self.response.out.write('No comment token')
      return
    if (tokenPush is None):
      self.response.out.write('No push token')
      return
    pr_number = str(data['number'])
    sha = data['pull_request']['merge_commit_sha']
    issueUrl = 'issues/' + pr_number
    labelsResult = self.urlGET(tokenPush, issueUrl + '/labels')
    hasMerge = False
    for l in json.loads(labelsResult.content):
      if l['name'] == merge_label:
        hasMerge = True
    if not hasMerge:
      return
    result = self.urlGET(tokenPush, issueUrl + '/events')
    if result.status_code == 200:
      mergeUser = None
      for e in json.loads(result.content):
        if e['event'] == 'labeled' and e['label']['name'] == merge_label:
          mergeUser = e['actor']['login'];
        if e['event'] == 'unlabeled' and e['label']['name'] == merge_label:
          mergeUser = None
      if (mergeUser == None):
        return
      self.response.out.write('Merge action? ' + str(mergeUser) + '\n')
      result = self.urlDELETE(tokenPush, issueUrl + '/labels/' + merge_label_uri_esc);
      if (CoreTeamMember.forUsername(mergeUser) == None):
        self.response.out.write(mergeUser + ' is not a core team member with merge privileges.')
        self.urlPOST(tokenComment, issueUrl + '/comments', {'body': 'User @' + mergeUser + ' does not have PR merging privileges.'})
        return
      if (mergeUser != None): 
        branch = 'presubmit-' + mergeUser + '-pr-' + pr_number
        self.urlPOST(tokenComment, issueUrl + '/comments', {'body': 'Merging PR #' + pr_number + ' on behalf of @' + mergeUser + ' to branch [' + branch + '](https://github.com/angular/angular/tree/' + branch + ').'})
        response = self.urlPOST(tokenPush, 'git/refs', {'ref': 'refs/heads/' + branch, 'sha': sha})
        if (response.status_code == 422):
          self.urlPATCH(tokenPush, 'git/refs/heads/' + branch, {'sha': sha, 'force': True})



app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/web_hook', WebHookPage)
], debug=True)
