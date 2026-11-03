const api=require('../../utils/api'),session=require('../../utils/session');
const options={feeding:['普通膳食','母乳喂养','配方喂养','混合喂养','辅食＋奶','不清楚'],appetite:['良好','一般','较前减少','不清楚'],change:['无明显变化','有所改善','有所加重','首次记录 / 不清楚'],adherence:['尚未制定方案','按计划执行','部分执行','存在困难']};
const symptomNames=['暂无明显不适','皮肤不适','消化道不适','呼吸道不适','其他'];
Page({data:{loading:true,busy:false,child:null,kind:'',title:'电子问卷',draftId:null,infant:false,options,
 answers:{feeding:'普通膳食',appetite:'一般',change:'首次记录 / 不清楚',adherence:'尚未制定方案',symptoms:[],avoid:'',substitute:'',concerns:'',birth_history:'',family:'',infant:'',symptom_notes:''},symptomChoices:symptomNames.map(value=>({value,checked:false}))},
 async onLoad(q){this.childId=Number(q.child);this.taskId=Number(q.task)||null;if(!Number.isInteger(this.childId)||this.childId<1||!session.valid(q.kind)){api.error(Error('问卷入口无效'));wx.redirectTo({url:'/pages/children/index'});return;}
 this.setData({kind:q.kind,title:session.kinds[q.kind]});session.setPending(q.kind);
 try{const detail=await api.request('/children/'+this.childId),draft=detail.questionnaires.find(x=>x.status==='draft'&&x.kind===session.kinds[q.kind]);
  const answers={...this.data.answers,feeding:detail.child.feeding,birth_history:detail.child.history,...(draft?draft.answers:{})};
  this.setData({child:detail.child,infant:(Date.now()-new Date(detail.child.birth).getTime())/2629800000<24,answers,draftId:draft?draft.id:null,symptomChoices:symptomNames.map(value=>({value,checked:(answers.symptoms||[]).includes(value)})),loading:false});
 }catch(e){api.error(e);}},
 input(e){this.setData({['answers.'+e.currentTarget.dataset.key]:e.detail.value});},
 pick(e){const key=e.currentTarget.dataset.key;this.setData({['answers.'+key]:options[key][Number(e.detail.value)]});},
 symptoms(e){let selected=e.detail.value;const hadNone=(this.data.answers.symptoms||[]).includes('暂无明显不适');if(selected.length>1&&selected.includes('暂无明显不适'))selected=hadNone?selected.filter(v=>v!=='暂无明显不适'):['暂无明显不适'];this.setData({'answers.symptoms':selected,symptomChoices:symptomNames.map(value=>({value,checked:selected.includes(value)}))});},
 async save(e){if(this.data.busy||this.data.loading)return;const status=e.currentTarget.dataset.status;if(status==='submitted'&&!this.data.answers.symptoms.length){api.error(Error('请选择近期症状情况'));return;}
 this.setData({busy:true});try{
  await api.request('/children/'+this.childId+'/questionnaires',{kind:session.kinds[this.data.kind],version:'1.0',status,answers:this.data.answers,id:this.data.draftId,task_id:status==='submitted'?this.taskId:null});
  if(status==='submitted'){session.clearPending();wx.redirectTo({url:'/pages/result/index?child='+this.childId+'&kind='+this.data.kind});}
  else{const detail=await api.request('/children/'+this.childId),draft=detail.questionnaires.find(q=>q.status==='draft'&&q.kind===session.kinds[this.data.kind]);this.setData({draftId:draft?draft.id:null});wx.showToast({title:'草稿已保存'});}
 }catch(err){api.error(err);}finally{this.setData({busy:false});}}
});
