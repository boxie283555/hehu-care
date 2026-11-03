const api=require('../../utils/api'),session=require('../../utils/session');
Page({
 data:{phone:'13800138000',code:'',devCode:'',busy:false,sending:false,countdown:0,title:'欢迎来到禾护',invalid:false},
 onLoad(options){const ok=session.capture(options);this.setData({invalid:!ok});const kind=session.pending();if(kind)this.setData({title:session.kinds[kind]});},
 async onShow(){if(wx.getStorageSync('hehu.token')&&!this.data.invalid){try{const u=await api.request('/me');if(u.role!=='guardian'){session.clearAuth();return;}wx.redirectTo({url:'/pages/children/index'});}catch(e){api.error(e);}}},
 input(e){this.setData({[e.currentTarget.dataset.key]:e.detail.value});},
 async sendCode(){if(this.data.sending||this.data.countdown)return;if(!/^1[3-9]\d{9}$/.test(this.data.phone)){api.error(Error('请输入有效手机号'));return;}
  this.setData({sending:true});try{const r=await api.request('/auth/code',{phone:this.data.phone});this.setData({devCode:r.dev_code||'',code:r.dev_code||'',countdown:60});this.timer=setInterval(()=>{const next=this.data.countdown-1;this.setData({countdown:next});if(!next)clearInterval(this.timer);},1000);}catch(e){api.error(e);}finally{this.setData({sending:false});}},
 async login(){if(this.data.busy)return;this.setData({busy:true});try{const r=await api.request('/auth/login',{phone:this.data.phone,code:this.data.code,role:'guardian',client:'miniprogram'});wx.setStorageSync('hehu.token',r.access_token);wx.redirectTo({url:'/pages/children/index'});}catch(e){api.error(e);}finally{this.setData({busy:false});}},
 onUnload(){clearInterval(this.timer);}
});
