const config=require('../config');
const session=require('./session');
function request(path,data) {
 return new Promise((resolve,reject)=>{
  const token=wx.getStorageSync('hehu.token');
  wx.request({url:config.apiBase.replace(/\/$/,'')+'/api'+path,method:data===undefined?'GET':'POST',data,
   header:{'content-type':'application/json',...(token?{Authorization:'Bearer '+token}:{})},timeout:15000,
   success(res){
    if(res.statusCode>=200&&res.statusCode<300){resolve(res.data);return;}
    if(res.statusCode===401){session.clearAuth();const pages=getCurrentPages();if(pages.length&&pages[pages.length-1].route!=='pages/entry/index')wx.reLaunch({url:'/pages/entry/index'});}
    reject(Error(res.data&&res.data.error||'请求失败，请稍后重试'));
   },fail(){reject(Error('无法连接服务，请检查后台是否启动及开发版地址配置'));}
  });
 });
}
function error(e){wx.showToast({title:e.message||'操作失败',icon:'none',duration:3500});}
module.exports={request,error};
