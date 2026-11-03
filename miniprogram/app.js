const session = require('./utils/session');
App({onLaunch(options) { session.capture(options.query || {}); }});
