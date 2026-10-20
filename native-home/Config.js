.pragma library

// Keep personal names, weather coordinates, and optional artwork in a local build.
var greetingNames = [];
var quoteText = "The real danger is not that computers will begin to think like men, but that men will begin to think like computers.";
var quoteAuthor = "Sydney J. Harris";
var showCharacters = true;
var weather = {enabled:false, label:"Weather", url:""};
// This layout has four tiles. Replace IDs with the IDs from your own inventory.
var apps = [
    {title:"Netflix", appId:"netflix", image:"netflix.png", color:"#000000", w:80, h:80, crop:false},
    {title:"JioHotstar", appId:"hotstar", image:"jiohotstar.png", color:"#6721cf", w:282, h:110, crop:true},
    {title:"Stremio", appId:"io.strem.tv", image:"stremio.png", color:"#7b5bf5", w:200, h:70, crop:false},
    {title:"YouTube", appId:"youtube.leanback.v4", image:"youtube.png", color:"#ffffff", w:170, h:110, crop:false}
];
