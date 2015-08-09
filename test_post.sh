 curl -X POST -d @sample.github.post http://localhost:8080/web_hook \
   --header "User-Agent: GitHub-Hookshot/044aadd" \
   --header "Content-Type: application/json" \
   --header "X-GitHub-Delivery: 12cd6c80-3d87-11e5-8956-a43037371557" \
   --header "X-GitHub-Event: pull_request" 
