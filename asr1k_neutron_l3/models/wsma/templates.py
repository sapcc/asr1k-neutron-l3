# Copyright 2017 SAP SE
#
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

EXEC_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<SOAP:Envelope xmlns:SOAP="http://schemas.xmlsoap.org/soap/envelope/"
xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/"
xmlns:xsd="http://www.w3.org/2001/XMLSchema"
xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
 <SOAP:Body>
  <request xmlns="urn:cisco:wsma-exec" correlator="{CORRELATOR}">
   <execCLI>
    <cmd>{EXEC_CMD}</cmd>
   </execCLI>
  </request>
 </SOAP:Body>
</SOAP:Envelope>"""

CONFIG_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<SOAP:Envelope xmlns:SOAP="http://schemas.xmlsoap.org/soap/envelope/"
xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/"
xmlns:xsd="http://www.w3.org/2001/XMLSchema"
xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
 <SOAP:Body>
  <request xmlns="urn:cisco:wsma-config" correlator="{correlator}">
   <configApply details="all">
    <config-data>
     <cli-config-data>
      <cmd>{command1}</cmd>
      <cmd>{command2}</cmd>
     </cli-config-data>
    </config-data>
   </configApply>
  </request>
 </SOAP:Body>
</SOAP:Envelope>"""
