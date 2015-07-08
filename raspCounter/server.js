var http = require("http");
var exec = require('exec');
var url = require("url");
var path = require("path");
var fs = require("fs");
var qs = require('querystring');
// Starts the server
var Start = function(route, serve, reqtype) {

    // Lauched when there is a request.
    var onRequest = function(request, response) {

        // Extracts the pathname from the url
        var pathname = url.parse(request.url).pathname;

        try {
            pathname = pathname.substring(1, pathname.length);
        } catch (err) {

        }

        // Responds to all requests apart from that for favicon.ico
     if (pathname !== "favicon.ico") {

            console.log("Request has been recieved");

            // Gets the path from the router

         var path = process.cwd() + "/"; // Sets up the path to the
         var corrected = false;

    if (pathname === "" || pathname === "index" || pathname === "home"
            || pathname === "index.html" || pathname === "home.html") {
        // If it should be routed to the home page.
        path += "index.html"; // Sets it to the index page
        corrected = true;

    } else {

        // If it isn't any of those, then just appends the pathname
        path += pathname;
    }

    
    var pathSplit = pathname.split(".");

    if (pathSplit.length === 1 && corrected === false) {
        // If the split leaves length one then appends .html to the end.
        path += ".html";

    }
           console.log("Path is : " + path);
            console.log("Path has been generated");
            // Gets html or whatever will be written from the pageserver
            var html = "";


          if (request.method == 'POST') {
            //STRAT POST 

            console.log("hello post recieved");
          console.log(request + " ");

          var body = '';
        request.on('data', function (data) {
            body += data;
            // 1e6 === 1 * Math.pow(10, 6) === 1 * 1000000 ~~~ 1MB
            if (body.length > 1e6) { 
                // FLOOD ATTACK OR FAULTY CLIENT, NUKE REQUEST
                request.connection.destroy();
            }
        });
        request.on('end', function () {

            var POST = qs.parse(body);
            // use POST

             var wifiname = POST.SSID;
             var wifipass = POST.wifipass;
             console.log("wifi:" +wifiname + " pass:" + wifipass);

             var myConf = "ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\n";
             myConf+= "update_config=1\n";
             myConf+="network={\n";
             myConf+="        ssid="+wifiname+"\n";
             myConf+="        ssid="+wifipass+"\n";
             myConf+="}\n";

             console.log(myConf);
             fs.writeFile("/etc/wpa_supplicant/wpa_supplicant.conf", myConf, function(err) {
                  if(err) {
                   return console.log(err);
                  }

                  console.log("The file was saved!");
              }); 


         

            // END POST
              html = fs.readFileSync('./confirm.html'); 


        
            console.log("Html has been generated");

        
            var type = "";
            var pathSplit = path.split(".");
            if (pathSplit === 1) {
              type = "plain";
            } else {

                type = pathSplit[1];
            }
            response.writeHead(200, {
                "Content-Type" : "text/" + type
            });
            // writes to output
            console.log("Writing to output");
            response.write(html);

               exec('/usr/local/cointraker/enrollment.sh',
              function (error, stdout, stderr) {
              console.log('stdout: ' + stdout);
              console.log('stderr: ' + stderr);
              if (error !== null) {
               console.log('exec error: ' + error);
              }
          });
            console.log("Written to output");
            // ends connection
            response.end();
 });
          }
          else { //START  GET

           html = fs.readFileSync(path); 


        
            console.log("Html has been generated");

        
            var type = "";
            var pathSplit = path.split(".");
            if (pathSplit === 1) {
              type = "plain";
            } else {

                type = pathSplit[1];
            }
            response.writeHead(200, {
                "Content-Type" : "text/" + type
            });
            // writes to output
            console.log("Writing to output");
            response.write(html);
            console.log("Written to output");
            // ends connection
            response.end();
            console.log("Request answered successfully");

         //END GET
          }

        } //favicon if



    };

    http.createServer(onRequest).listen(80);
    console.log("Server has been started");
};

exports.Start = Start;


