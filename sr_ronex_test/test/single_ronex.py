#!/usr/bin/env python
# ####################################################################
# Copyright (c) 2013, Shadow Robot Company, All rights reserved.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3.0 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.
# ####################################################################

import rospy, sys, getopt, unittest, rostest
import dynamic_reconfigure.client

from time import sleep
from string import Template
from threading import Lock
# from sr_ronex_msgs.msg import BoolArray
from sr_ronex_msgs.msg import GeneralIOState
from std_msgs.msg import UInt16MultiArray
from std_msgs.msg import Bool

class TestContainer( unittest.TestCase ):
  """
  A class used to test the Shadow Robot ethercat board HW.
  
  For the test to succeed 2 ronex modules are required
  each with a stacker on it
  The digital I/O of one module should be connected to the I/O of the other
  The analogue I/O of one of the modules should be connected to a constant voltage source
  
  On each module
  12 digital inputs/outputs
  6 PWM outputs
  12 analogue inputs

  The digital inputs will read back the value we set for the outputs.
  Then all the I/O should switch roles from Input to Output and vice versa
  The PWM outputs will be set to their lower frequency, and the digital inputs used to check the on-off period
  The analogue inputs should be wired to an appropriate constant voltage source
  """

  def setUp( self ):
    self.find_ronexes()
    self.init_clients_publishers_subscribers()
    self.state_lock = Lock()

    self.state = [ None, None ]
    self.result = False

    self.params_i = { "input_mode_" + str( i ) : True for i in xrange( 12 ) }
    self.params_o = { "input_mode_" + str( i ) : False for i in xrange( 12 ) }


  def find_ronexes( self ):
    attempts = 50
    while attempts:
      try:
        rospy.get_param( "/ronex/devices/0/ronex_id" )
        break
      except:
        if attempts == 50:
          rospy.loginfo( "Waiting for the ronex to be loaded properly." )
        sleep( 0.1 )
        attempts -= 1
    self.assertNotEqual( attempts, 0, "Failed to get ronex devices from parameter server" )

    self.ronex_devs = rospy.get_param( "/ronex/devices" )
    self.assertEqual( len( self.ronex_devs ), 2, "Error. Connect a ronex bridge with 2 ronex devices" )

  def init_clients_publishers_subscribers( self ):
    basic = "/ronex/general_io/"
    ron = [ basic + str( self.ronex_devs[str( i )]["serial"] ) for i in xrange( 2 ) ]

    com_dig = "/command/digital/"
    com_pwm = "/command/pwm"
    sta = "/state"

    self.clients = [ dynamic_reconfigure.client.Client( r ) for r in ron ]
    self.digital_publishers = [ [ rospy.Publisher( r + com_dig + str( i ), Bool, latch = True ) for i in xrange( 12 ) ] for r in ron ]
    self.subscriber_0 = rospy.Subscriber( ron[0] + sta, GeneralIOState, self.state_callback_0 )
    self.subscriber_1 = rospy.Subscriber( ron[1] + sta, GeneralIOState, self.state_callback_1 )

  def state_callback_0( self, msg ):
    with self.state_lock:
      self.state[0] = msg

  def state_callback_1( self, msg ):
    with self.state_lock:
      self.state[1] = msg

  def digital_test_case( self, outr, inr, message ):
    self.result = False
    self.set_ronex_io_state( outr, inr )
    for i, bool in enumerate( message ):
      self.digital_publishers[outr][i].publish( bool )
    rospy.sleep( 0.1 )

    with self.state_lock:
      self.result = ( self.state[inr].digital == message )

  def set_ronex_io_state( self, outr, inr ):

    self.clients[ outr ].update_configuration( self.params_o )
    self.clients[ inr ].update_configuration( self.params_i )

    rospy.sleep( 0.2 )

# the following tests will be performed
  def test_change_state_one( self ):
    self.set_ronex_io_state( 0, 1 )

    config_0 = self.clients[0].get_configuration()
    config_1 = self.clients[1].get_configuration()

    for param, value in self.params_o.iteritems():
      self.assertEqual( config_0[param], value, "Failed in first attempt to set digital I/O state" )
    for param, value in self.params_i.iteritems():
      self.assertEqual( config_1[param], value, "Failed in first attempt to set digital I/O state" )

  def test_change_state_two( self ):
    self.set_ronex_io_state( 1, 0 )

    config_0 = self.clients[0].get_configuration()
    config_1 = self.clients[1].get_configuration()

    for param, value in self.params_i.iteritems():
      self.assertEqual( config_0[param], value, "Failed in second attempt to set digital I/O state" )
    for param, value in self.params_o.iteritems():
      self.assertEqual( config_1[param], value, "Failed in second attempt to set digital I/O state" )

  def test_digital_all_true( self ):
    message = 12 * [True]
    self.digital_test_case( 0, 1, message )
    self.assertTrue( self.result, "digital i/o test failure" )
    self.digital_test_case( 1, 0, message )
    self.assertTrue( self.result, "digital i/o test failure" )

  def test_digital_all_false( self ):
    message = 12 * [False]
    self.digital_test_case( 0, 1, message )
    self.assertTrue( self.result, "digital i/o test failure" )
    self.digital_test_case( 1, 0, message )
    self.assertTrue( self.result, "digital i/o test failure" )

  def test_digital_odd_true( self ):
    message = 6 * [True, False]
    self.digital_test_case( 0, 1, message )
    self.assertTrue( self.result, "digital i/o test failure" )
    self.digital_test_case( 1, 0, message )
    self.assertTrue( self.result, "digital i/o test failure" )

  def test_digital_even_true( self ):
    message = 6 * [False, True]
    self.digital_test_case( 0, 1, message )
    self.assertTrue( self.result, "digital i/o test failure" )
    self.digital_test_case( 1, 0, message )
    self.assertTrue( self.result, "digital i/o test failure" )

if __name__ == '__main__':
  rospy.init_node( 'single_ronex' )
  rostest.rosrun( 'sr_ronex_tests', 'single_ronex', TestContainer )
