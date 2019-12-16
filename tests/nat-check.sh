#!/usr/local/bin/bash
#set +x 
DEBUG='> /dev/null 2>&1'
#DEBUG=""

RED="\033[1;31m"
GREEN="\033[1;32m"
NOCOLOR="\033[0m"

SSHUSER="root"
#SSHOPTIONS="-o ConnectTimeout=2"
JUMPHOST="-J my.jump.host"
JUMPPREFIX="-J my.jump.host,"
PUBLICNET="192.168"

if test -f "./nat-check.env"; then
    source ./nat-check.env
fi

declare -a rips=("10.236.42.5" "$PUBLICNET.233.101" "10.236.42.10" "10.236.43.2")
declare -a fips=("10.236.42.31" "10.236.42.7" "10.236.42.23" "$PUBLICNET.233.99" "10.236.42.3" "10.236.42.15" "10.236.43.10" "$PUBLICNET.233.102" "$PUBLICNET.233.98" "10.236.41.200")
declare -a nips=("10.180.100.25" "10.180.200.7" "10.180.0.8" "10.180.50.8")
declare -a lips=("10.236.41.200" "10.236.41.201" "10.180.0.21" "10.180.100.20" "10.180.111.8")
declare -A lips_jump=( ["10.236.41.200"]="" ["10.236.41.201"]="" ["10.180.0.21"]=",$SSHUSER@10.236.42.31" ["10.180.100.20"]=",$SSHUSER@130.214.233.98" ["10.180.111.8"]=",$SSHUSER@10.236.42.7")
declare -A nips_jump=( ["10.180.100.25"]="10.236.42.15" ["10.180.200.7"]="10.236.42.23" ["10.180.0.8"]="10.236.42.31" ["10.180.50.8"]="10.236.43.10" )
declare -A nips_gw=( ["10.180.100.25"]="10.236.42.5" ["10.180.200.7"]="130.214.233.101" ["10.180.0.8"]="10.236.42.10" ["10.180.50.8"]="10.236.43.2" )

echo -e "Checking local connectivity\n to floating ip"
for ip in "${fips[@]}"
do
    ping -i0.2 -c2 -q $ip  > /dev/null 2>&1
    exit_status=$?
    if [ $exit_status -eq 0 ]; then
        echo -e "${GREEN}  $ip${NOCOLOR}"
    else
        echo -e "${RED}  $ip${NOCOLOR}"
    fi
done

echo -e " to router ip"
for ip in "${rips[@]}"
do
    ping -i0.2 -c2 -q $ip  > /dev/null 2>&1
    exit_status=$?
    if [ $exit_status -eq 0 ]; then
        echo -e "${GREEN}  $ip${NOCOLOR}"
    else
        echo -e "${RED}  $ip${NOCOLOR}"
    fi
done

for host in "${fips[@]}"
do
  echo -e "Checking Connectivity from host $host\n to floating ip"
  for ip in "${fips[@]}"
  do
  #if [[ "$host" == "$ip" ]]; then
  #continue
  #fi
      echo -n "  $ip "
      ssh $SSHOPTIONS $JUMPHOST $SSHUSER@$host ping -i0.2 -c 2 -q $ip  > /dev/null 2>&1
      exit_status=$?
      if [ $exit_status -eq 0 ]; then
          echo -en "${GREEN}icmp ${NOCOLOR}"
      else
          echo -en "${RED}icmp ${NOCOLOR}"
      fi

      ssh $SSHOPTIONS $JUMPHOST $SSHUSER@$host nc -w2 -z -n -v $ip 22 > /dev/null 2>&1
      exit_status=$?
      if [ $exit_status -eq 0 ]; then
          echo -e "${GREEN}tcp ${NOCOLOR}"
      else
          echo -e "${RED}tcp ${NOCOLOR}"
      fi
  done

  echo -e " to router ip"
  for ip in "${rips[@]}"
  do
      echo -n "  $ip "
      ssh $SSHOPTIONS $JUMPHOST $SSHUSER@$host ping -i0.2 -c 2 -q $ip  > /dev/null 2>&1
      exit_status=$?
      if [ $exit_status -eq 0 ]; then
          echo -e "${GREEN}icmp ${NOCOLOR}"
      else
          echo -e "${RED}icmp ${NOCOLOR}"
      fi
  done
done

for host in "${nips[@]}"
do
  echo -e ${nips_jump[$host]}
  echo -e "Checking Connectivity from host $host(${nips_gw[$host]})\n to floating ip"
  for ip in "${fips[@]}"
  do
      echo -n "  $ip "
      ssh $SSHOPTIONS $JUMPPREFIX$SSHUSER@${nips_jump[$host]} $SSHUSER@$host ping -i0.2 -c 2 -q $ip $DEBUG
      exit_status=$?
      if [ $exit_status -eq 0 ]; then
          echo -en "${GREEN}icmp ${NOCOLOR}"
      else
          echo -en "${RED}icmp ${NOCOLOR}"
      fi

      ssh $SSHOPTIONS $JUMPPREFIX$SSHUSER@${nips_jump[$host]} $SSHUSER@$host nc -w2 -z -n -v $ip 22 $DEBUG
      exit_status=$?
      if [ $exit_status -eq 0 ]; then
          echo -e "${GREEN}tcp ${NOCOLOR}"
      else
          echo -e "${RED}tcp ${NOCOLOR}"
      fi
  done

  echo -e "to router ip"
  for ip in "${rips[@]}"
  do
      echo -n "  $ip "
      ssh $SSHOPTIONS $JUMPPREFIX$SSHUSER@${nips_jump[$host]} $SSHUSER@$host ping -i0.2 -c 2 -q $ip  $DEBUG
      exit_status=$?
      if [ $exit_status -eq 0 ]; then
          echo -e "${GREEN}icmp ${NOCOLOR}"
      else
          echo -e "${RED}icmp ${NOCOLOR}"
      fi
  done
done

echo -e "Checking L3VPN connectivity"
for host in "${lips[@]}"
do
  echo -e " Checking Connectivity from $host"
  for ip in "${lips[@]}"
  do
      echo -n "  $ip "
      ssh $SSHOPTIONS $JUMPHOST${lips_jump[$host]} $SSHUSER@$host ping -i0.2 -c 2 -q $ip $DEBUG
      exit_status=$?
      if [ $exit_status -eq 0 ]; then
          echo -en "${GREEN}icmp ${NOCOLOR}"
      else
          echo -en "${RED}icmp ${NOCOLOR}"
      fi

      ssh $SSHOPTIONS $JUMPHOST${lips_jump[$host]} $SSHUSER@$host nc -w2 -z -n -v $ip 22 $DEBUG
      exit_status=$?
      if [ $exit_status -eq 0 ]; then
          echo -e "${GREEN}tcp ${NOCOLOR}"
      else
          echo -e "${RED}tcp ${NOCOLOR}"
      fi
  done
done
