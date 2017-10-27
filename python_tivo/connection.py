import logging
import socket
import select
import threading
import time

from . import const
from . import response

class TiVoError(Exception):
  pass

class TiVoSocketError(Exception):
  pass

class ThreadedSocket(object):
  def __init__(self, host, port):
    self._host = host
    self._port = port
    self._data = b""
    self._timeoutLock = threading.Lock()
    self._timeout = None
    self._connect()

  def send(self, data):
    self._sock.sendall(data)

  def wait(self, timeout = 0):
    self._timeoutLock.acquire()
    self._timeout = time.time() + timeout
    self._timeoutLock.release()
    self._recvThread.join()
    return self._data

  def _connect(self):
    self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self._sock.settimeout(10)
    self._sock.connect((self._host, self._port))
    self._sock.setblocking(0)
    self._recvThread = threading.Thread(target = self._receive)
    self._recvThread.start()

  def _receive(self):
    while True:
      try:
        self._timeoutLock.acquire()
        timeout = self._timeout
        self._timeoutLock.release()
        if timeout and time.time() >= timeout:
          raise TimeoutError()

        ready = select.select([self._sock], [], [], 0.5)
        if ready[0]:
          data = self._sock.recv(4096)
          self._data += data
      except:
        self._sock.close()
        return False

class TiVoConnection(object):
  def __init__(self, host, port):
    self._host = host
    self._port = port
    self._sendCommandsLock = threading.Lock()

  def sendCommands(self, commands):
    try:
      self._sendCommandsLock.acquire()

      sock = ThreadedSocket(self._host, self._port)

      if len(commands) > 0:
        # Leave some time to receive the first message before sending anything
        time.sleep(0.1)

        for command in commands:
          if command.startswith("WAIT "):
            try:
              timeToSleep = float(command[5:])
              time.sleep(timeToSleep)
            except ValueError:
              pass
          else:
            fullCommand = command + "\r"
            sock.send(fullCommand.encode("utf-8"))
            time.sleep(0.1)

      allData = sock.wait(1.0)
  
      if len(allData) == 0:
        return []

      allData = allData.decode("utf-8")
      allResponses = allData.split("\r")
      allResponses = filter(None, allResponses)
      parsedResponses = list(map(self._parseResponse, allResponses))
      return parsedResponses
    except:
      raise TiVoSocketError()
    finally:
      self._sendCommandsLock.release()

  @staticmethod
  def _readFromSocket(sock, timeout):
    allData = b""
    begin = time.time()
    while True and time.time() - begin < timeout:
      ready = select.select([sock], [], [], timeout)
      print("Ready {}".format(ready))
      if ready[0]:
        data = sock.recv(4096)
        allData += data
      else:
        break
    return allData

  def fetchOnState(self):
    responses = self.sendCommands([])
    return len(responses) > 0

  def setOnState(self, state):
    on = self.fetchOnState()
    if on == state:
      return

    commands = None
    if state:
      commands = ["IRCODE STANDBY"]
    else:
      commands = ["IRCODE STANDBY", const.SpecialCommand.WAIT(0.5), "IRCODE STANDBY"]

    self.sendCommands(commands)

  def fetchCurrentChannel(self):
    responses = self.sendCommands([])
    if len(responses) == 0:
      return None

    lastResponse = responses[0]
    return response.FullChannelName(lastResponse)

  def setChannel(self, channel):
    responses = self.sendCommands(["SETCH " + channel])
    if len(responses) == 0:
      return False

    lastResponse = responses[-1]
    if not response.IsChannelStatus(lastResponse):
      return False

    return lastResponse["channel"] == channel.zfill(4)

  def forceChannel(self, channel):
    responses = self.sendCommands(["FORCECH " + channel])
    if len(responses) == 0:
      return False

    lastResponse = responses[-1]
    if not response.IsChannelStatus(lastResponse):
      return False

    return lastResponse["channel"] == channel.zfill(4)

  def sendIRCode(self, code):
    return self.sendCommands(["IRCODE " + code])

  def sendKeyboard(self, code):
    return self.sendCommands(["KEYBOARD " + code])

  def sendTeleport(self, code):
    return self.sendCommands(["TELEPORT " + code])

  @staticmethod
  def _parseResponse(message):
    split = message.split(" ")
    type = split[0]
    response = {
      "raw": message,
      "type": type
    }
    
    if type == const.ResponseType.CH_STATUS:
      response["channel"] = split[1]
      response["reason"] = split[-1]
      response["subChannel"] = split[2] if len(split) == 4 else None
    elif type == const.ResponseType.CH_FAILED:
      response["reason"] = split[1]

    return response
