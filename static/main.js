function deleteFile(name){
    fetch("/delete/"+name)
    .then(()=>location.reload());
}
