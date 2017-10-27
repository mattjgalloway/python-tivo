from . import const

def IsChannelStatus(response):
  return response["type"] == const.ResponseType.CH_STATUS

def IsInvalidKey(response):
  return response["type"] == const.ResponseType.INVALID_KEY

def FullChannelName(response):
  if not IsChannelStatus(response):
    return None

  fullChannel = response['channel']
  if response['subChannel']:
    fullChannel += "-"
    fullChannel += response["subChannel"]

  return fullChannel
