SCRIPT_DIR=$( cd -- "$( dirname -- "${bash_source[0]}" )" &> /dev/null && pwd ) 

EXTMODS_DIR=/var/cache/salt/minion/extmods
BASE_FILES_DIR=/var/cache/salt/minion/files/base
AP_OPT_SALT_DIR=/opt/autopi/salt
CORE_REPO_BASE=$SCRIPT_DIR/src/salt/base
BACKUPS_DIR=$SCRIPT_DIR/backups

UTILS_DIR=$CORE_REPO_BASE/ext/_utils
ENGINES_DIR=$CORE_REPO_BASE/ext/_engines
RETURNERS_DIR=$CORE_REPO_BASE/ext/_returners
MODULES_DIR=$CORE_REPO_BASE/ext/_modules
STATES_DIR=$CORE_REPO_BASE/ext/_states

declare -A FILE_LOCATOR
FILE_LOCATOR["can_conn.py"]=$UTILS_DIR
FILE_LOCATOR["can_obd_conn.py"]=$UTILS_DIR
FILE_LOCATOR["can_manager.py"]=$ENGINES_DIR
FILE_LOCATOR["elm327_proxy.py"]=$UTILS_DIR
FILE_LOCATOR["common_util.py"]=$UTILS_DIR
FILE_LOCATOR["obd_conn.py"]=$UTILS_DIR
FILE_LOCATOR["threading_more.py"]=$UTILS_DIR
FILE_LOCATOR["battery_util.py"]=$UTILS_DIR

declare -a location_list

verbose=false
no_restart=false
force=false

cpy_uflag="-u"          # Changed by 'force=True'

print_help() {
    echo -e "\
Move changed files between local dev env, Core repository and salt cache
Use options -l -r -c in order to set the direction of the move. Minimum 2 locations must be specified (or none for default). 
! Copying from Cache is not allowed.
! LOCAL currently currently disabled for safety

Example: -r -l (or -rl) - [Repo] > [Local] 
Default: [Repo] > [Cache]

move.sh [options]      
    -v[erbose]              Verbose output
    -n[o restart]           Disables restarting the salt minion
    -f[orce]                Copies all files instead of just the updated files

    Locations:
    -l                      [Local] (DISABLED)
    -r                      [Repo]
    -c                      [Cache]
"
}

print_location_list() {
    local list=("$@")
    local output=""

    for element in "${list[@]}"; do
        output+="[$element] > "
    done

    # Remove the last " > " from the output string using sed
    output=$(echo "$output" | sed 's/ > $//')

    echo "$output"
}

copy_local_to_repo() {
    echo -e "\n---[ COPYING FROM LOCAL TO REPO ]---"
    for FILE in ${!FILE_LOCATOR[@]}
    do
        cp $SCRIPT_DIR/local_ext/$FILE ${FILE_LOCATOR[$FILE]} -v $cpy_uflag
    done
}

copy_local_to_cache() {
    echo -e "\n---[ COPYING FROM LOCAL TO CACHE ]---"
    for FILE in ${!FILE_LOCATOR[@]}
    do
        bn=$(basename ${FILE_LOCATOR[$FILE]})
        cp -v $cpy_uflag $SCRIPT_DIR/local_ext/$FILE $EXTMODS_DIR/"${bn:1}/"
        cp -v $cpy_uflag $SCRIPT_DIR/local_ext/$FILE $BASE_FILES_DIR/_"${bn:1}/"
    done
}

copy_repo_to_local() {
    echo -e "\n---[ COPYING FROM REPO TO LOCAL ]---"
    for FILE in ${!FILE_LOCATOR[@]}
    do
        cp ${FILE_LOCATOR[$FILE]}/$FILE $SCRIPT_DIR/local_ext -v $cpy_uflag
    done
}

copy_repo_to_cache() {
    echo -e "\n---[ COPYING FROM REPO TO SALT CACHE ]---"
    for dir in $CORE_REPO_BASE/ext/_* ; do bn=$(basename $dir) ; cp -v -r $cpy_uflag $dir/*.py $EXTMODS_DIR/"${bn:1}"; done
    for dir in $CORE_REPO_BASE/ext/_* ; do bn=$(basename $dir) ; cp -v -r $cpy_uflag $dir/*.py $BASE_FILES_DIR/$bn; done
}

restart_minion() {
    echo -e "\n---[ RESTARTING SALT MINION ]---"
    systemctl restart salt-minion
}

backup() {
    local location=("$@")
    local LDIR=$BACKUPS_DIR/$location
    mkdir -p $LDIR

    case $location in
		"Local") backup_local $LDIR;;
        "Repo" ) backup_repo $LDIR;;
        "Cache") backup_cache $LDIR;;
    esac
}

backup_local() {
    TO_DIR=("$@")
    cp -r $SCRIPT_DIR/local_ext/* $TO_DIR
}

backup_repo() {
    TO_DIR=("$@")
    cp -r $CORE_REPO_BASE/ext/* $TO_DIR
}

backup_cache() {
    TO_DIR=("$@")
    cp -r $EXTMODS_DIR $TO_DIR
    cp -r $BASE_FILES_DIR  $TO_DIR
}

while getopts vrhlcnf flag
do
    case "${flag}" in
		v) verbose=true;;
        n) no_restart=true;;
        h) print_help; exit 0;;
        l) location_list+=("Local") & echo "[Local] location currently disabled" && exit 1;;
        r) location_list+=("Repo");;
        c) location_list+=("Cache");;
        f) force=true;;
        *) print_help; exit 1;;
    esac
done

if [ ${#location_list[@]} -eq 0 ]; then
    location_list=("Repo" "Cache")
elif [ ${#location_list[@]} -eq 1 ]; then
    print_help
    exit 1
fi

if [ "$force" = true ]; then
    cpy_uflag=""
else
    cpy_ulfag="-u"
fi

echo Doing code copy: $(print_location_list "${location_list[@]}")

for (( i=0; i<${#location_list[@]}-1; i++ )); do
    from=${location_list[i]}
    to=${location_list[i+1]}

    if [ $from == "Cache" ]; then
        echo "Copying from Cache is not allowed!"
        exit 1
    fi

    backup $to

    if [[ $from == "Local" && $to == "Repo" ]]; then
        copy_local_to_repo
    elif [[ $from == "Repo" && $to == "Cache" ]]; then
        copy_repo_to_cache
    elif [[ $from == "Local" && $to == "Cache" ]]; then
        copy_local_to_cache
    elif [[ $from == "Repo" && $to == "Local" ]]; then
        copy_repo_to_local
    fi
done

if [ $no_restart == false ]; then
    restart_minion
fi