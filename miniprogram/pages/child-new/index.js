const api=require('../../utils/api'),session=require('../../utils/session');
Page({data:{sexes:['女','男'],feedings:['普通膳食','母乳喂养','配方喂养','混合喂养','辅食＋奶','不清楚'],form:{name:'',sex:'女',birth:'',feeding:'普通膳食',allergies:'',history:''},consent:false,busy:false,today:session.today()},
 input(e){this.setData({['form.'+e.currentTarget.dataset.key]:e.detail.value});},
 picker(e){const key=e.currentTarget.dataset.key;this.setData({['form.'+key]:key==='birth'?e.detail.value:(key==='sex'?this.data.sexes:this.data.feedings)[Number(e.detail.value)]});},
 consent(e){this.setData({consent:e.detail.value.includes('yes')});},
 async save(){if(this.data.busy)return;if(!this.data.consent){api.error(Error('请确认监护授权'));return;}this.setData({busy:true});try{const c=await api.request('/children',{...this.data.form,consent:true});const kind=session.pending();wx.redirectTo({url:kind?'/pages/questionnaire/index?child='+c.id+'&kind='+kind:'/pages/health/index?child='+c.id});}catch(e){api.error(e);}finally{this.setData({busy:false});}}
});
