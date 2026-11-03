const api=require('../../utils/api'),session=require('../../utils/session');
Page({data:{children:[],loading:true,title:'选择孩子',pending:''},
 async onShow(){if(!wx.getStorageSync('hehu.token')){wx.reLaunch({url:'/pages/entry/index'});return;}const kind=session.pending();this.setData({pending:kind,title:kind?session.kinds[kind]:'孩子的健康空间',loading:true});try{const children=await api.request('/children');this.setData({children});}catch(e){api.error(e);}finally{this.setData({loading:false});}},
 choose(e){const id=e.currentTarget.dataset.id;wx.navigateTo({url:this.data.pending?'/pages/questionnaire/index?child='+id+'&kind='+this.data.pending:'/pages/health/index?child='+id});},
 create(){wx.navigateTo({url:'/pages/child-new/index'});},
 async logout(){try{await api.request('/auth/logout',{});session.clearAuth();wx.reLaunch({url:'/pages/entry/index'});}catch(e){api.error(e);}}
});
