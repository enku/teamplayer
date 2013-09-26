{% load staticfiles %}
// This is ffmp3's js but pointing to the internal flash and turning tracking
// off
var MRP=function(){}
MRP.setObject=function(){eval("MRP.instance = document."+MRP.objectId+";");if(MRP.instance==null)MRP.instance=document.getElementById(MRP.objectId);}
MRP.setElementId=function(id){MRP.elementId=id;}
MRP.setObjectId=function(id){MRP.objectId=id;MRP.setObject();}
MRP.play=function(){MRP.instance.playSound();}
MRP.stop=function(){MRP.instance.stopSound();}
MRP.setVolume=function(v){MRP.instance.setVolume(v/100);}
MRP.showInfo=function(info){MRP.instance.showInfo(info);}
MRP.setTitle=function(title){MRP.instance.setTitle(title);}
MRP.setUrl=function(url){MRP.instance.setUrl(url);}
MRP.setFallbackUrl=function(fallbackUrl){MRP.instance.setFallbackUrl(fallbackUrl);}
MRP.setCallbackFunction=function(f){musesCallback=f;}
MRP.callbackExists=function(){var type="error";type=typeof musesCallback;return type!="undefined"&&type!="error";}
MRP.insert=function(p){if(p.wmode==null)p.wmode="window";if(p.id==null)p.id=MRP.objectId;var flashvars="url="+p.url;flashvars+="&lang="+(p.lang!=null?p.lang:"auto");flashvars+="&codec="+p.codec;flashvars+="&tracking=false";flashvars+="&volume="+(p.volume!=null?p.volume:100);if(p.introurl!=null)flashvars+="&introurl="+p.introurl;if(p.autoplay!=null)flashvars+="&autoplay="+(p.autoplay?"true":"false");if(p.jsevents!=null)flashvars+="&jsevents="+(p.jsevents?"true":"false");if(p.buffering!=null)flashvars+="&buffering="+p.buffering;if(p.metadataProxy!=null)flashvars+="&metadataproxy="+p.metadataProxy;if(p.reconnectTime!=null)flashvars+="&reconnecttime="+p.reconnectTime;if(p.fallbackUrl!=null)flashvars+="&fallback="+p.fallbackUrl;if(p.skin.indexOf("/")==-1){if(p.skin=="original"||p.skin=="tiny")flashvars+="&skin="+p.skin;else flashvars+="&skin={% static "ffmp3/ffmp3-eastanbul.xml" %}";}else flashvars+="&skin="+p.skin;flashvars+="&title="+p.title;flashvars+="&welcome="+p.welcome;var swf="{% static "ffmp3/muses.swf" %}";var domparams="width=\""+p.width+"\" height=\""+p.height+"\" ";if(p.bgcolor!=null)domparams+="bgcolor=\""+p.bgcolor+"\" ";var c="<object id=\""+p.id+"\" classid=\"clsid:D27CDB6E-AE6D-11cf-96B8-444553540000\" "+domparams+">";c+="<param name=\"movie\" value=\""+swf+"\" />";c+="<param name=\"flashvars\" value=\""+flashvars+"\" />";c+="<param name=\"wmode\" value=\""+p.wmode+"\" />";c+="<param name=\"allowScriptAccess\" value=\"always\" />";c+="<param name=\"scale\" value=\"noscale\" />";if(p.bgcolor!=null)c+="<param name=\"bgcolor\" value=\""+p.bgcolor+"\" />";c+="<embed name=\""+p.id+"\" src=\""+swf+"\" flashvars=\""+flashvars+"\" scale=\"noscale\" wmode=\""+p.wmode+"\" "+domparams+" allowScriptAccess=\"always\" type=\"application/x-shockwave-flash\" />";c+="</object>";if(p.callbackFunction!=null)MRP.setCallbackFunction(p.callbackFunction);else if(p.jsevents==true&&!MRP.callbackExists())MRP.setCallbackFunction(function(e,v){});if(p.elementId==null&&MRP.elementId!=null)p.elementId=MRP.elementId;if(p.elementId==null)document.write(c);else document.getElementById(p.elementId).innerHTML=c;MRP.setObject();}
MRP.main=function(){}
MRP.objectId="MRPObject";MRP.main();
