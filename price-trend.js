(function(root){'use strict';
function previous(month,n){const [y,m]=month.split('-').map(Number);return new Date(Date.UTC(y,m-1-n,1)).toISOString().slice(0,7);}
function classify(points,month){const prices=new Map(points.map(p=>[p.month,p.price])),now=prices.get(month),one=prices.get(previous(month,1)),two=prices.get(previous(month,2)),three=prices.get(previous(month,3));
if(!Number.isFinite(now)||!Number.isFinite(one))return '待核验';
if(now>one)return '上行';if(now===one)return '平稳';
return Number.isFinite(two)&&Number.isFinite(three)&&one>two&&two>three?'回调':'下行';}
root.MaterialPriceTrend={classify};if(typeof module!=='undefined')module.exports=root.MaterialPriceTrend;
})(typeof window==='undefined'?globalThis:window);
