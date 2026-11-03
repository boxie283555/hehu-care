const session=require('../../utils/session');
Page({data:{title:'问卷已提交'},onLoad(q){this.childId=Number(q.child);this.setData({title:(session.kinds[q.kind]||'问卷')+'已提交'});},health(){wx.redirectTo({url:'/pages/health/index?child='+this.childId});},home(){wx.reLaunch({url:'/pages/children/index'});}});
