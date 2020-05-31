const {createProxyMiddleware} = require("http-proxy-middleware");

module.exports = function(app) {
  app.use(
    createProxyMiddleware(["/generate"], { target: "http://localhost:5000" })
  );
};