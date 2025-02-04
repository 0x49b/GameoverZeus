/**
This file defines the commands that can be invoked on a host via RPC
*/
namespace py HostActions

exception OverlordException {
  1: string why
}

service OverlordClient {
    /**
    Starts the given runnable with the given params
    :param kwargs: The keyword arguments to be passed to the runnable as a json-encoded dictionary
    :throws OverlordException: Thrown if the runnable could not be started.
    */
   void startRunnable(1:string importmodule, 2:string command, 3:string kwargs) throws (1:OverlordException oops),
   /**
    Starts the given runnable. Does nothing if that runnable does not exist or is not running.
    :throws OverlordException: Thrown if the runnable could not be started.
    */
   void stopRunnable(1:string command) throws (1:OverlordException oops),
   /** returns the host id */
   i32 getID()
}