const kinds = {initial:'首次综合评估', nutrition:'生长与营养随访', symptoms:'过敏症状随访'};
function valid(kind) { return Object.prototype.hasOwnProperty.call(kinds, kind); }
function pending() { const v=wx.getStorageSync('hehu.pending'); return valid(v)?v:''; }
function capture(options) {
 let kind=options.questionnaire;
 if (options.scene) {try {kind=decodeURIComponent(options.scene);} catch (_) {kind='';}}
 if (kind === undefined) return true;
 if (!valid(kind)) {wx.removeStorageSync('hehu.pending');return false;}
 wx.setStorageSync('hehu.pending',kind);return true;
}
function setPending(kind) {if(!valid(kind))throw Error('问卷类型无效');wx.setStorageSync('hehu.pending',kind);}
function clearPending() {wx.removeStorageSync('hehu.pending');}
function clearAuth() {wx.removeStorageSync('hehu.token');wx.removeStorageSync('hehu.user');}
function today(){const d=new Date();return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');}
module.exports={today,kinds,valid,pending,capture,setPending,clearPending,clearAuth};
